# TycoonBuild
_A /r/openttd tool_

### Where are the builds?

This tool generates builds that are pushed to [redditopenttd/openttd](https://hub.docker.com/r/redditopenttd/openttd/).

## About TycoonBuild

TycoonBuild is an automated tool designed to make maintenance of OpenTTD Docker builds far less painful.

Right now, it:
 * scrapes the _openttd.org_ finger server (http://finger.openttd.org/versions.txt) every 60 seconds
 * detects any changes / new versions and saves their state to `builds.json`
 * dispatches required builds to a (local) Docker server
 * correctly tags and pushes them once build is complete
 * updates `builds.json` with state after build is complete to indicate that the build was successful, and not to repeat builds for that version
 
TycoonBuild is currently very focused on building packages for `redditopenttd/openttd`, but it should be easy to fork to suit your individual needs. Pull requests making it more agnostic are much appreciated.