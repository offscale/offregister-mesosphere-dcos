from functools import partial
from os import path
from sys import modules

from offregister_fab_utils.ubuntu.systemd import disable_service
from offregister_fab_utils.yum import yum_depends
from offutils import pp
from pkg_resources import resource_filename

from fabric.context_managers import cd
from fabric.contrib.files import append, exists
from fabric.operations import sudo, run, put

from offregister_fab_utils.fs import cmd_avail
from yaml import load


def housekeeping0(*args, **kwargs):
    if sudo('docker ps', warn_only=True, quiet=True).failed:
        raise EnvironmentError('Expected Docker. Include offregister-docker in your config.')

    disable_service('firewalld')

    sudo('mkdir -p /var/lib/dcos /var/lib/mesos')
    append('/etc/sudoers', '%wheel ALL=(ALL) NOPASSWD: ALL', use_sudo=True)

    if not cmd_avail('timedatectl') and run('timedatectl', quiet=True, warn_only=True):
        raise EnvironmentError('Expected NTP to be enabled.')

    yum_depends('tar', 'xz', 'unzip', 'curl', 'ipset')

    append('/etc/environment', 'LANG={enc}\nLC_ALL={enc}'.format(enc='en_US.utf-8'), use_sudo=True)

    # <Cluster node>
    if sudo("grep -F 'SELINUX=permissive' /etc/selinux/config", warn_only=True, quiet=True).failed:
        sudo('sed -i s/SELINUX=enforcing/SELINUX=permissive/g /etc/selinux/config')
        did_something = False
        for group in ('nogroup', 'docker'):
            if sudo('grep -Fq {group} /etc/group'.format(group=group)):
                sudo('groupadd {group}'.format(group=group))
                did_something = True
        if did_something:
            sudo('reboot')
    # </Cluster node>

    run('mkdir -p ~/Downloads')
    with cd('~/Downloads'):
        sh = 'dcos_generate_config.sh'
        if not exists(sh):
            run('curl -L https://downloads.dcos.io/dcos/stable/{sh} -o {sh}'.format(sh=sh))


def configure1(*args, **kwargs):
    config_join = partial(path.join,
                          path.join(path.dirname(
                              resource_filename(modules[__name__].__package__, '__init__.py')), '_config'))

    run('mkdir -p ~/genconf')

    with open(config_join('config.yaml')) as f:
        d = load(f)
        d['agent_list'] = []
        pp(d)

    run('touch ~/genconf/ipdetect')
    with open(config_join('ipdetect.bash')) as f:
        put(f, '~/genconf/ipdetect')
