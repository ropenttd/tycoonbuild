import time, datetime, requests, os, json
import docker


def logThis(msg, end='\n'):
    print(datetime.datetime.now().strftime("%x %H:%M:%S | " + msg), end=end)


class Scraper(object):
    def Scrape(self):
        page = requests.get('http://finger.openttd.org/versions.txt')
        if page.status_code == 200:
            self.page = page.text
            self.data = []  # clean house
            for data in self.page.splitlines():
                data = data.split('\t')
                thisver = {'version': data[0], 'date': data[1], 'branch': data[2],
                           'tag': (data[3] if len(data) == 4 else None)}
                self.data.append(thisver)
            logThis("Scrape succeeded: ", end='')
        else:
            logThis("Scrape failed!")

    def Process(self):
        newJobsFlag = False
        for target, data in self.targets.items():

            buildTarget = next((x for x in self.data if x.get('tag', None) == target), False)
            if not buildTarget:
                continue

            if buildTarget['version'].startswith('<'):
                preVersion = buildTarget['version']

                buildTarget['version'] = \
                next((x for x in self.data if x.get('tag', None) == buildTarget['version'][1:-1]), False)[
                    'version']  # this should never fail (?)

                logThis("Target version " + preVersion + " appears to be a metaref, targeting " + buildTarget[
                    'version'] + " instead")

            buildTarget['tags'] = data['tags']  # we tag early so that we can easily compare

            if self.knownBuilds.get(target, {}) == buildTarget:
                # we already have the build, but have we processed it?
                if self.finishedBuilds.get(target, {}) == buildTarget:
                    logThis("Target " + data['branch'] + '/' + target + ': version ' + buildTarget[
                        'version'] + " already built, skipping")
                    continue
                else:
                    logThis("Build target for " + data['branch'] + '/' + target + ': version ' + buildTarget[
                        'version'] + " detected as failed, requeuing")
            else:
                logThis("New build target for " + data['branch'] + '/' + target + ': version ' + buildTarget['version'])
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
            logThis("Building " + job['version'] + " for " + job['tag'] + ", tagging as " + ','.join(job['tags']))
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
        self.targets = {'stable': {'tags': ['stable', 'latest'], 'branch': 'releases'},
                        'testing': {'tags': ['rc'], 'branch': 'releases'}}
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
