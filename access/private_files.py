"""Owner-only credential files on both NTFS and POSIX filesystems."""
import os
import subprocess


def _acl(path, *, set_permissions=False):
    script = r'''
$ErrorActionPreference = 'Stop'
$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
$path = $env:PORTAL_PRIVATE_CREDENTIAL_PATH
if ($env:PORTAL_SET_PRIVATE_ACL -eq '1') {
    $acl = [System.Security.AccessControl.FileSecurity]::new()
    $acl.SetOwner($sid)
    $acl.SetAccessRuleProtection($true, $false)
    $rule = [System.Security.AccessControl.FileSystemAccessRule]::new($sid, 'FullControl', 'Allow')
    $acl.AddAccessRule($rule)
    [System.IO.File]::SetAccessControl($path, $acl)
}
$acl = [System.IO.File]::GetAccessControl($path)
$rules = @($acl.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier]))
if ($rules.Count -eq 0 -or @($rules | Where-Object { $_.IdentityReference -ne $sid -or $_.IsInherited }).Count -gt 0) { exit 1 }
'''
    env = os.environ.copy()
    env['PORTAL_PRIVATE_CREDENTIAL_PATH'] = str(path.resolve())
    env['PORTAL_SET_PRIVATE_ACL'] = '1' if set_permissions else '0'
    return subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
        env=env, capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW).returncode == 0


def make_private(path):
    if os.name == 'nt':
        if not _acl(path, set_permissions=True):
            raise OSError('Could not protect the private credential file.')
    else:
        path.chmod(0o600)


def is_private(path):
    return _acl(path) if os.name == 'nt' else path.stat().st_mode & 0o077 == 0
