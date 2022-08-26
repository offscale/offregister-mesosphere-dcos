from functools import partial
from os import path
from sys import modules

from fabric.contrib.files import append, exists
from offregister_fab_utils.fs import cmd_avail
from offregister_fab_utils.ubuntu.systemd import disable_service
from offregister_fab_utils.yum import yum_depends
from offutils import pp
from pkg_resources import resource_filename
from yaml import load


def housekeeping0(c, *args, **kwargs):
    if c.sudo("docker ps", warn=True, hide=True).exited != 0:
        raise EnvironmentError(
            "Expected Docker. Include offregister-docker in your config."
        )

    disable_service(c, "firewalld")

    c.sudo("mkdir -p /var/lib/dcos /var/lib/mesos")
    append("/etc/sudoers", "%wheel ALL=(ALL) NOPASSWD: ALL", use_sudo=True)

    if not cmd_avail(c, "timedatectl") and c.run("timedatectl", hide=True, warn=True):
        raise EnvironmentError("Expected NTP to be enabled.")

    yum_depends("tar", "xz", "unzip", "curl", "ipset")

    append(
        "/etc/environment",
        "LANG={enc}\nLC_ALL={enc}".format(enc="en_US.utf-8"),
        use_sudo=True,
    )

    # <Cluster node>
    if (
        c.sudo(
            "grep -F 'SELINUX=permissive' /etc/selinux/config", warn=True, hide=True
        ).exited
        != 0
    ):
        c.sudo("sed -i s/SELINUX=enforcing/SELINUX=permissive/g /etc/selinux/config")
        did_something = False
        for group in ("nogroup", "docker"):
            if c.sudo("grep -Fq {group} /etc/group".format(group=group)):
                c.sudo("groupadd {group}".format(group=group))
                did_something = True
        if did_something:
            c.sudo("reboot")
    # </Cluster node>

    c.run("mkdir -p ~/Downloads")
    with c.cd("~/Downloads"):
        sh = "dcos_generate_config.sh"
        if not exists(c, runner=c.run, path=sh):
            c.run(
                "curl -L https://downloads.dcos.io/dcos/stable/{sh} -o {sh}".format(
                    sh=sh
                )
            )


def configure1(*args, **kwargs):
    config_join = partial(
        path.join,
        path.join(
            path.dirname(
                resource_filename(modules[__name__].__package__, "__init__.py")
            ),
            "_config",
        ),
    )

    c.run("mkdir -p ~/genconf")

    with open(config_join("config.yaml")) as f:
        d = load(f)
        d["agent_list"] = []
        pp(d)

    c.run("touch ~/genconf/ipdetect")
    with open(config_join("ipdetect.bash")) as f:
        c.put(f, "~/genconf/ipdetect")
