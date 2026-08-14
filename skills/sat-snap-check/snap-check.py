#!/usr/bin/env python3
"""Snap Delivery Checker — deterministic script.

Fetches snap RPM data from ohsnap, extracts git commits from tracked packages,
looks up PR merge commits from GitHub, and compares them to determine if
upstream PRs have been delivered in a downstream snap.

Usage:
    python3 snap-check.py \
        --snap 185 \
        --ohsnap-url https://ohsnap.sat.engineering.redhat.com \
        --prs "SAT-44612=https://github.com/Katello/katello/pull/11724"

Requires: gh CLI authenticated (gh auth login) or GH_TOKEN env var.

Output: JSON to stdout with delivery status for each PR.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
import ssl
import subprocess
import sys
import urllib.request

RPM_TO_REPO = {
    'rubygem-hammer_cli_foreman_rh_cloud-': 'theforeman/hammer-cli-foreman-rh-cloud',
    'rubygem-hammer_cli_katello-': 'Katello/hammer-cli-katello',
    'rubygem-hammer_cli_foreman-': 'theforeman/hammer-cli-foreman',
    'rubygem-hammer_cli-': 'theforeman/hammer-cli',
    'rubygem-foreman-tasks-': 'theforeman/foreman-tasks',
    'rubygem-foreman_kubevirt-': 'theforeman/foreman_kubevirt',
    'rubygem-foreman_bootdisk-': 'theforeman/foreman_bootdisk',
    'rubygem-foreman_puppet-': 'theforeman/foreman_puppet',
    'rubygem-foreman_remote_execution-': 'theforeman/foreman_remote_execution',
    'rubygem-foreman_leapp-': 'theforeman/foreman_leapp',
    'rubygem-foreman_openscap-': 'theforeman/foreman_openscap',
    'rubygem-katello-': 'Katello/katello',
    'rubygem-foreman_rh_cloud-': 'theforeman/foreman_rh_cloud',
    'rubygem-foreman_theme_satellite-': 'RedHatSatellite/foreman_theme_satellite',
    'rubygem-foreman_virt_who_configure-': 'theforeman/foreman_virt_who_configure',
    'foremanctl-': 'theforeman/foremanctl',
    'foreman-installer-': 'theforeman/foreman-installer',
    'foreman-proxy-': 'theforeman/smart-proxy',
    'foreman-': 'theforeman/foreman',
}

FOREMAN_SUBPKGS = [
    'foreman-installer',
    'foreman_rh_cloud',
    'foreman_maintain',
    'foreman-selinux',
    'foreman-dynflow',
    'foreman-debug',
    'foreman-cli',
    'foreman-doc',
    'foreman-libvirt',
    'foreman-vmware',
    'foreman-ec2',
    'foreman-gce',
    'foreman-openstack',
    'foreman-ovirt',
    'foreman-journald',
    'foreman-service',
    'foreman-telemetry',
    'foreman-postgresql',
    'foreman-redis',
    'foreman-assets',
    'foreman-pcp',
    'foreman-proxy',
]

HAMMER_CLI_SUBPKGS = ['rubygem-hammer_cli_foreman_', 'rubygem-hammer_cli_foreman_rh_cloud-', 'rubygem-hammer_cli_katello-']


def fetch_json(url, skip_ssl=False):
    """Fetch JSON from a non-GitHub URL (ohsnap)."""
    req = urllib.request.Request(url)
    ctx = None
    if skip_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        return json.loads(resp.read().decode())


def gh_api(endpoint):
    """Call GitHub API via gh CLI for reliable rate-limit handling and retries."""
    result = subprocess.run(
        ['gh', 'api', endpoint],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f'gh api failed for {endpoint}')
    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


def extract_snap_rpms(snap_data):
    results = {}
    all_rpms = set()
    for repo_data in snap_data:
        for rpm in repo_data.get('rpms', repo_data.get('srpms', [])):
            all_rpms.add(rpm)

    for rpm in all_rpms:
        for prefix, gh_repo in RPM_TO_REPO.items():
            if prefix == 'foreman-' and any(x in rpm for x in FOREMAN_SUBPKGS):
                continue
            if prefix == 'rubygem-hammer_cli-' and any(
                rpm.startswith(x) for x in HAMMER_CLI_SUBPKGS
            ):
                continue
            if prefix == 'rubygem-hammer_cli_foreman-' and 'rubygem-hammer_cli_foreman_' in rpm:
                continue
            if rpm.startswith(prefix):
                # e.g. "...20260801032415gitdf11ba7.el9sat..."
                commit_match = re.search(r'git([a-f0-9]{7,})', rpm)
                # git-describe format, e.g. "...169.gdae6d89.el9sat..."
                if not commit_match:
                    commit_match = re.search(r'\.g([a-f0-9]{7,})\.', rpm)
                # build timestamp preceding the git commit
                ts_match = re.search(r'(\d{14})git', rpm)
                if gh_repo not in results or commit_match:
                    results[gh_repo] = {
                        'rpm': rpm,
                        'commit': commit_match.group(1) if commit_match else None,
                        'build_ts': ts_match.group(1) if ts_match else None,
                    }
                break
    return results


def parse_pr_url(url):
    m = re.match(r'https://github\.com/([^/]+)/([^/]+)/pull/(\d+)', url)
    if m:
        return m.group(1), m.group(2), int(m.group(3))
    return None, None, None


def get_pr_info(owner, repo, number):
    data = gh_api(f'repos/{owner}/{repo}/pulls/{number}')
    return {
        'merge_commit_sha': data.get('merge_commit_sha'),
        'merged_at': data.get('merged_at'),
        'merged': data.get('merged', False),
        'html_url': data.get('html_url'),
    }


def compare_commits(owner, repo, base, head):
    data = gh_api(f'repos/{owner}/{repo}/compare/{base}...{head}')
    return {
        'status': data.get('status'),
        'ahead_by': data.get('ahead_by', 0),
        'behind_by': data.get('behind_by', 0),
    }


def get_version_tag_sha(owner, repo, version):
    for tag_name in (version, f'v{version}'):
        try:
            data = gh_api(f'repos/{owner}/{repo}/git/ref/tags/{tag_name}')
            obj = data.get('object', {})
            sha = obj.get('sha', '')
            if obj.get('type') == 'tag':
                tag_data = gh_api(f'repos/{owner}/{repo}/git/tags/{sha}')
                sha = tag_data.get('object', {}).get('sha', sha)
            return sha
        except Exception:
            continue
    return None


def get_stable_branch_sha(owner, repo, version):
    """Try to find a stable branch for tagged releases (e.g. 2.y-stable, 3.12-stable).

    Fails gracefully for repos without stable branches — caller falls back to version tag.
    """
    major = version.split('.')[0]
    major_minor = '.'.join(version.split('.')[:2])
    for branch in [f'{major}.y-stable', f'{major_minor}-stable']:
        try:
            data = gh_api(f'repos/{owner}/{repo}/git/ref/heads/{branch}')
            return data.get('object', {}).get('sha'), branch
        except Exception:
            continue
    return None, None


def check_cherry_pick(owner, repo, branch, tag_version, pr_number):
    """Check if a PR was cherry-picked to a branch by scanning commit messages."""
    try:
        data = gh_api(f'repos/{owner}/{repo}/compare/{tag_version}...{branch}')
        for commit in data.get('commits', []):
            msg = commit.get('commit', {}).get('message', '')
            if f'#{pr_number}' in msg or f'pull/{pr_number}' in msg:
                return True, commit.get('sha', '')[:7]
        return False, None
    except Exception:
        return False, None


def extract_version_from_rpm(rpm_name):
    m = re.search(r'-(\d+\.\d+\.\d+)-', rpm_name)
    return m.group(1) if m else None


def check_pr(jira_key, pr_url, snap_rpms, prev_snap_rpms=None):
    if '/issues/' in pr_url and '/pull/' not in pr_url:
        return {
            'jira_key': jira_key,
            'pr_url': pr_url,
            'error': 'GitHub Issue field contains an issue URL, not a PR URL. '
            'Please update the field with the pull request URL.',
        }
    owner, repo, number = parse_pr_url(pr_url)
    if not owner:
        return {
            'jira_key': jira_key,
            'pr_url': pr_url,
            'error': f'Could not parse PR URL: {pr_url}',
        }

    full_repo = f'{owner}/{repo}'
    snap_rpm = snap_rpms.get(full_repo)
    if not snap_rpm:
        return {
            'jira_key': jira_key,
            'pr_url': pr_url,
            'pr_repo': full_repo,
            'pr_number': number,
            'error': f'Repo {full_repo} not found in snap RPMs',
        }

    try:
        pr_info = get_pr_info(owner, repo, number)
    except Exception as e:
        return {
            'jira_key': jira_key,
            'pr_url': pr_url,
            'pr_repo': full_repo,
            'pr_number': number,
            'error': f'Failed to fetch PR info: {e}',
        }

    merge_sha = pr_info.get('merge_commit_sha')
    if not merge_sha:
        return {
            'jira_key': jira_key,
            'pr_url': pr_url,
            'pr_repo': full_repo,
            'pr_number': number,
            'error': 'PR has no merge commit (not merged?)',
        }

    snap_commit = snap_rpm.get('commit')
    version = extract_version_from_rpm(snap_rpm['rpm'])

    if not snap_commit and version:
        # Try stable branch first — handles -2, -3 rebuilds with cherry-picks
        stable_sha, stable_branch = get_stable_branch_sha(owner, repo, version)
        if stable_sha:
            snap_commit = stable_sha
            snap_rpm = {**snap_rpm, 'commit': stable_sha, 'stable_branch': stable_branch}
        else:
            tag_sha = get_version_tag_sha(owner, repo, version)
            if tag_sha:
                snap_commit = tag_sha
                snap_rpm = {**snap_rpm, 'commit': tag_sha, 'tag': version}

    if not snap_commit:
        if prev_snap_rpms:
            prev_rpm = prev_snap_rpms.get(full_repo, {})
            prev_version = extract_version_from_rpm(prev_rpm.get('rpm', ''))
            curr_version = extract_version_from_rpm(snap_rpm.get('rpm', ''))
            if prev_version and curr_version and prev_version == curr_version:
                return {
                    'jira_key': jira_key,
                    'pr_url': pr_url,
                    'pr_repo': full_repo,
                    'pr_number': number,
                    'pr_merge_sha': merge_sha[:7],
                    'pr_merged_at': pr_info.get('merged_at'),
                    'snap_rpm': snap_rpm.get('rpm'),
                    'snap_commit': None,
                    'status': 'ahead',
                    'delivered': False,
                    'reason': f'RPM version unchanged from previous snap ({curr_version})',
                }
        return {
            'jira_key': jira_key,
            'pr_url': pr_url,
            'pr_repo': full_repo,
            'pr_number': number,
            'pr_merge_sha': merge_sha[:7],
            'pr_merged_at': pr_info.get('merged_at'),
            'snap_rpm': snap_rpm.get('rpm'),
            'snap_commit': None,
            'status': 'manual_check',
            'delivered': False,
            'reason': 'No git commit in RPM and no version tag found',
        }

    try:
        cmp = compare_commits(owner, repo, snap_commit, merge_sha)
    except Exception as e:
        return {
            'jira_key': jira_key,
            'pr_url': pr_url,
            'pr_repo': full_repo,
            'pr_number': number,
            'pr_merge_sha': merge_sha[:7],
            'pr_merged_at': pr_info.get('merged_at'),
            'snap_commit': snap_commit[:7] if snap_commit and len(snap_commit) > 7 else snap_commit,
            'snap_rpm': snap_rpm.get('rpm'),
            'error': f'GitHub compare failed: {e}',
        }

    delivered = cmp['status'] in ('behind', 'identical')

    # For diverged results on a stable branch, check for cherry-picks
    if cmp['status'] == 'diverged' and snap_rpm.get('stable_branch') and version:
        cherry_picked, cherry_sha = check_cherry_pick(
            owner, repo, snap_rpm['stable_branch'], version, number
        )
        if cherry_picked:
            delivered = True
            cmp['cherry_pick_sha'] = cherry_sha

    result = {
        'jira_key': jira_key,
        'pr_url': pr_url,
        'pr_repo': full_repo,
        'pr_number': number,
        'pr_merge_sha': merge_sha[:7],
        'pr_merged_at': pr_info.get('merged_at'),
        'snap_commit': snap_commit[:7] if snap_commit and len(snap_commit) > 7 else snap_commit,
        'snap_rpm': snap_rpm.get('rpm'),
        'status': cmp['status'],
        'ahead_by': cmp['ahead_by'],
        'behind_by': cmp['behind_by'],
        'delivered': delivered,
    }
    if snap_rpm.get('tag'):
        result['snap_tag'] = snap_rpm['tag']
    if snap_rpm.get('stable_branch'):
        result['stable_branch'] = snap_rpm['stable_branch']
    if cmp.get('cherry_pick_sha'):
        result['cherry_pick_sha'] = cmp['cherry_pick_sha']
    return result


def main():
    parser = argparse.ArgumentParser(description='Snap Delivery Checker')
    parser.add_argument('--snap', help='Snap version (e.g., 185)')
    parser.add_argument('--snap-data', help='Inline JSON snap data (alternative to --snap)')
    parser.add_argument(
        '--ohsnap-url',
        default='https://ohsnap.sat.engineering.redhat.com',
        help='ohsnap base URL',
    )
    parser.add_argument(
        '--prs',
        required=True,
        help='Comma-separated JIRA_KEY=PR_URL pairs',
    )
    args = parser.parse_args()

    # Verify gh CLI is available
    try:
        subprocess.run(['gh', '--version'], capture_output=True, timeout=5)
    except FileNotFoundError:
        json.dump(
            {'error': 'gh CLI not found. Install from https://cli.github.com/ and run: gh auth login'},
            sys.stdout,
            indent=2,
        )
        sys.exit(1)

    if args.snap:
        version = args.snap if '.' in args.snap else f'{args.snap}.0'
        url = f'{args.ohsnap_url}/api/releases/stream/snaps/{version}/rpms?all=true'
        try:
            snap_data = fetch_json(url, skip_ssl=True)
        except Exception as e:
            json.dump({'error': f'Failed to fetch ohsnap data: {e}'}, sys.stdout, indent=2)
            sys.exit(1)
    elif args.snap_data:
        snap_data = json.loads(args.snap_data)
    else:
        json.dump({'error': 'Either --snap or --snap-data is required'}, sys.stdout, indent=2)
        sys.exit(1)

    snap_rpms = extract_snap_rpms(snap_data)

    prev_snap_rpms = None
    if args.snap:
        snap_num = args.snap.split('.')[0]
        prev_version = f'{int(snap_num) - 1}.0'
        prev_url = f'{args.ohsnap_url}/api/releases/stream/snaps/{prev_version}/rpms?all=true'
        try:
            prev_data = fetch_json(prev_url, skip_ssl=True)
            prev_snap_rpms = extract_snap_rpms(prev_data)
        except Exception:
            pass

    pr_pairs = []
    for pair in args.prs.split(','):
        pair = pair.strip()
        if '=' in pair:
            key, url = pair.split('=', 1)
            pr_pairs.append((key.strip(), url.strip()))

    results = []
    errors = []

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(check_pr, jira_key, pr_url, snap_rpms, prev_snap_rpms): jira_key
            for jira_key, pr_url in pr_pairs
        }
        for future in as_completed(futures):
            result = future.result()
            if 'error' in result:
                errors.append(result)
            else:
                results.append(result)

    output = {
        'snap_version': args.snap or 'inline',
        'snap_rpms': {k: v for k, v in snap_rpms.items()},
        'results': sorted(results, key=lambda r: r.get('delivered', False), reverse=True),
        'errors': errors,
    }

    json.dump(output, sys.stdout, indent=2)
    print()


if __name__ == '__main__':
    main()
