import time, datetime, requests, os, json
import docker


def logThis(msg, end='\n'):
    print(datetime.datetime.utcnow().strftime("%x %H:%M:%S | " + msg), end=end)


class Scraper(object):
    def Scrape(self):
        # finger.openttd.org doesn't track the latest releases anymore, rip
        page = requests.get('https://openttd.ams3.digitaloceanspaces.com/openttd-releases/listing.txt')
        if page.status_code == 200:
            self.page = page.text
            self.data = []  # clean house
            for data in self.page.splitlines():
                data = data.split(',')
                thisver = {'version': data[0], 'date': data[1], 'tag': data[2]}
                self.data.append(thisver)
            logThis("Scrape succeeded: ", end='')
        else:
            logThis("Scrape failed!")

    def Process(self):
        newJobsFlag = False
        for target, data in self.targets.items():
            allPossibleBuildTargets = list(x for x in self.data
                                if x.get('tag', None) == data.get('tag')
                                and data.get('search', '').upper() in x.get('version').upper()
                                )

            buildTarget = max(allPossibleBuildTargets, key=(lambda key: datetime.datetime.strptime(key['date'], "%Y-%m-%d %H:%M UTC")))
            newestBuildTarget = max(self.data, key=(lambda key: datetime.datetime.strptime(key['date'], "%Y-%m-%d %H:%M UTC")))
            if buildTarget is None:
                continue

            if buildTarget != newestBuildTarget:
                preVersion = buildTarget['version']
                buildTarget['version'] = newestBuildTarget['version']

                logThis("Target version " + preVersion + " appears to be outdated, targeting " + buildTarget[
                    'version'] + " instead")

            buildTarget['tags'] = data['tags']  # we tag early so that we can easily compare

            if self.knownBuilds.get(target, {}) == buildTarget:
                # we already have the build, have we processed it?
                if self.finishedBuilds.get(target, {}) == buildTarget:
                    logThis("Target " + target + ': version ' + buildTarget[
                        'version'] + " already built, skipping")
                    continue
                else:
                    logThis("Build target for " + target + ': version ' + buildTarget[
                        'version'] + " detected as failed, requeuing")
            else:
                logThis("New build target for " + target + ': version ' + buildTarget['version'])
            self.knownBuilds[target] = buildTarget
            self.jobs.append(buildTarget)
            newJobsFlag = True
        self.SaveState()
        if not newJobsFlag:
            logThis("No new targets")
        return newJobsFlag

    def DispatchJobs(self):
        garbage = []
        for job in self.jobs:
            logThis("Building " + job['version'] + " for " + ','.join(job['tags']))
            image = self.docker.images.build(
                path=os.environ.get('DOCKER_BUILDDIR', '/Users/duck/Documents/Workbench/Docker/OpenTTD'),
                rm=True,
                buildargs={'OPENTTD_VERSION': job['version']},
                tag=self.repo + ':' + job['version'])
            for tag in job['tags']:
                image.tag(self.repo, tag)
            logThis("done!")
            garbage.append(job)

        logThis("Builds complete, uploading (this might take a moment)")
        self.docker.images.push(self.repo)
        for job in garbage:
            self.finishedBuilds[job['tag']] = job
            self.jobs.remove(job)

        logThis("Upload complete")
        self.SaveState()

    def LoadState(self):
        try:
            with open('builds.json') as fp:
                try:
                    filedata = json.load(fp)
                    self.knownBuilds = filedata.get('known', {})
                    self.finishedBuilds = filedata.get('built', {})
                    logThis("Loaded builds from builds.json")
                except json.decoder.JSONDecodeError:
                    json.dump({}, open('builds.json', 'w'))
        except FileNotFoundError:
            pass

    def SaveState(self):
        with open('builds.json', 'w') as fp:
            json.dump({'known': self.knownBuilds, 'built': self.finishedBuilds}, fp)

    @classmethod
    def Run(cls, scraper):
        cls.Scrape(scraper)
        newjobs = cls.Process(scraper)
        if newjobs:
            # Dey took our jerbs!
            logThis("Processing new jobs")
            cls.DispatchJobs(scraper)

    def __init__(self):
        self.data = []
        self.targets = {'stable': {'tag': 'stable', 'tags': ['stable', 'latest']},
                        'testing_rc': {'tag': 'testing', 'tags': ['rc'], 'search': 'RC'},
                        'testing_beta': {'tag': 'testing', 'tags': ['beta'], 'search': 'beta'}}
        self.jobs = []
        self.knownBuilds = {}
        self.finishedBuilds = {}
        self.LoadState()
        self.repo = 'redditopenttd/openttd'
        self.docker = docker.from_env()
        if os.environ.get('DOCKER_USER', False):
            try:
                self.docker.login(os.environ.get('DOCKER_USER', None), os.environ.get('DOCKER_PASS', None))
            except docker.errors.DockerException as e:
                print(e)


if __name__ == '__main__':
    scraper = Scraper()
    while True:
        Scraper.Run(scraper)
        time.sleep(60)
