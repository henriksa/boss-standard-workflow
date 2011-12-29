#!/usr/bin/python
"""
Bugzilla participant

Interacts with bugzilla to:
* add comments to bugs
* change bug status
* verify bug mentioned

The comment can be populated using a string or a template.

.. warning::
   The get_relevant_changelog participant should have be run first to fetch
   the relevant changelog entries

:term:`Workitem` fields IN

:Parameters:
   ev.actions(list):
      submit request data structure :term:`actions`.
   package(string):
      name of the package being handled, if actions is not provided.
   relevant_changelog(list):
      a field containing changelog entries in a list, if actions is not provided
   platform(string):
     The name of the platform to which the packages belong. This is used to
     select which bug trackers to talk to according to the configuration file.

:term:`Workitem` params IN

:Parameters:
   status(string):
      UNCONFIRMED/NEW/ASSIGNED/REOPENED/RESOLVED/VERIFIED/CLOSED
   resolution(string):
      FIXED/INVALID/WONTFIX/DUPLICATE/WORKSFORME/MOVED
   comment(string):
      Comment for the bug
   template(string):
      File locally readable in the path specified
      used as a Template (passed the wi hash for values lookup)

:term:`Workitem` fields OUT

:Returns:
    result(boolean):
       True if everything was OK, False otherwise.


https://wiki.mozilla.org/index.php?title=Bugzilla:REST_API:Methods
"""

import re, os
import urllib2, urllib
from urllib2 import HTTPError
import datetime
import json

from Cheetah.Template import Template, NotFound

from boss.bz.xmlrpc import BugzillaXMLRPC
from boss.bz.rest import BugzillaREST

def prepare_comment(template, template_data):
    """ Generate the comment to be added to the bug on bugzilla

    :param template: Cheetah template
    :type template: string
    :param template_data: dictionary that contains the data items (refer workitem JSON hash description)
    :type template_data: dict

    """
    template_data['time'] = datetime.datetime.ctime(datetime.datetime.today())
    try:
        text = Template(template, searchList=template_data )
    except NotFound, e:
        print "Template NotFound exception"
        print "#"*79
        print template
        print "#"*79
        print json.dumps(template_data,sort_keys=True, indent=4)
        print "#"*79
        raise

    comment = { "text" : "%s" % ( text ) }
    return comment

def bz_opener(bugzilla, url, method=None, data=None):
    """
    This is where the HTTP communication with the bugzilla REST API happens
    
    :param bugzilla: the configuration data structure constructed from the config file
    :type bugzilla: dict
    :param url: the constructed REST API call
    :type url: string
    :param method: HTTP method to override the default POST/GET, to support PUT
    :type method: string
    :param data: The REST API call JSON data used in a POST request
    :type data: object

    """
    uri = bugzilla['bugzilla_server'] + bugzilla['rest_slug']
    user = bugzilla['bugzilla_user']
    passwd = bugzilla['bugzilla_pwd']

    pwmgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
    pwmgr.add_password(realm=None,
                       uri=uri,
                       user=user,
                       passwd=passwd)
    auth_handler = urllib2.HTTPBasicAuthHandler(pwmgr)

    opener = urllib2.build_opener(auth_handler)
    opener.addheaders = [
        ('Content-Type', 'application/json'),
        ('Accept', 'application/json'),
        ]

    if "Bugzilla_login" in bugzilla['cookies']:
        print "Old url %s" % url
        url = (url + "?userid="
               + bugzilla['cookies']['Bugzilla_login']
               + "&cookie="
               + bugzilla['cookies']['Bugzilla_logincookie'])
        print "New url %s" % url

    if not data:
        return json.loads(opener.open(uri + url).read())
    else:
        req = urllib2.Request(uri + url, data = json.dumps(data))
        req.add_header('Content-Type', 'application/json')
        req.add_header('Accept', 'application/json')
        if method:
            req.get_method = lambda: method
        return json.loads(opener.open(req).read())

def get_bug(bugzilla, bugid):
    """
    Constructs a bugzilla REST API call to get a bug

    :param bugzilla:  the configuration data structure constructed from the config file
    :type bugzilla: dict
    :param bugid: the number of the bug to be retrieved
    :type bugid: string

    """
    return bz_opener(bugzilla, 'bug/%s' % bugid)

def put_bug(bugzilla, bugid, bug):
    """
    Constructs a bugzilla REST API call to modify a bug

    :param bugzilla:  the configuration data structure constructed from the config file
    :type bugzilla: dict
    :param bugid: the number of the bug to be retrieved
    :type bugid: string
    :param bug: the modified bug data object
    :type bugid: object

    """
    return bz_opener(bugzilla, 'bug/%s' % bugid, method="PUT", data=bug)

def bz_state_comment(bugzilla, bugnum, status, resolution, wi):
    """
    Gets a bug object, modifies it as specified and then saves it to bugzilla

    :param bugzilla:  the configuration data structure constructed from the config file
    :type bugzilla: dict
    :param bugnum: the number of the bug to be retrieved
    :type bugnum: string
    :param status: the new status to be set
    :type status: string
    :param resolution: the new resolution to be set
    :type statuts: string
    :param wi: the workitem object
    :type wi: object

    """
    if bugzilla['method'] != 'REST':
        print "Not implemented"
        return False

    bug = get_bug(bugzilla, bugnum)

    comment = ""
    if wi.params.comment:
        comment = comment = { "text" : "%s" % ( wi.params.comment ) }
    elif wi.params.template and os.path.isfile(wi.params.template):
        with open(wi.params.template) as f:
            comment = prepare_comment(f.read(), wi.to_h())
    else:
        comment = prepare_comment(bugzilla["template"], wi.to_h())

    nbug = {}
    if "version" in bugzilla and bugzilla['version'] == '0.8':
        # old version of REST API
        token_name ='token'
    else:
        token_name ='update_token'
    if token_name in bug:
        nbug['token'] = bug[token_name]
    else:
        print "This isn't going to work...."

    # Initially set to the original status and resolution
    if "status" in bug:
        nbug['status'] = bug['status']
    if "resolution" in bug:
        nbug['resolution'] = bug['resolution']

    # and if new ones are specified, set them
    if status:
        nbug['status'] = status
    if resolution:
        nbug['resolution'] = resolution

    nbug["comments"] = [comment]
    #year, week, day = datetime.date.isocalendar(datetime.datetime.today())
    #milestone = "%d-%02d" % (year, week)
    #nbug["target_milestone"] = milestone
    result = put_bug(bugzilla, bugnum, nbug)
    # FIXME: use result
    return True


def get_bug_attr(bugzilla, bugnum, attr):
    """
    Gets a bug attribute

    :param bugzilla:  the configuration data structure constructed from the config file
    :type bugzilla: dict
    :param bugnum: the number of the bug to be retrieved
    :type bugnum: string
    :param attr: the name of an attribute whose value is needed
    :type attr: string

    """

    if bugzilla['method'] != 'REST':
        print "Not implemented"
        return None
    bug = get_bug(bugzilla, bugnum)
    if attr in bug.keys():
        return bug[attr]
    else:
        return None

def handle_mentioned_bug(bugzilla, bugnum, wi, results):
    """
    Gets a bug attribute

    :param bugzilla:  the configuration data structure constructed from the config file
    :type bugzilla: dict
    :param bugnum: the number of the bug to be retrieved
    :type bugnum: string
    :param wi: the workitem object
    :type wi: object
    :param results: results collection
                    {msg = f.msg,
                    bugnums = [],
                    cbugnums = [],
                    fbugnums = [],}

    :type results: dict

    """
    result = False
    try:
        status = wi.params.status
        resolution = wi.params.resolution
        result = bz_state_comment(bugzilla, bugnum, status,
                                  resolution, wi)
    except HTTPError, e:
        print_http_debug(e)

    # TODO: updating parameter is bad. Use return value of the function
    if result:
        results["cbugnums"].append(bugnum)
    else:
        results["fbugnums"].append(bugnum)

def print_http_debug(e):
    """ Helper utility function to pretty print an HTTP exception

    :param e: The exception
    :type e: Exception

    """

    print "-"*60
    if hasattr(e, "code"):
        print e.code
    if hasattr(e, "read"):
        print e.read()
    if hasattr(e, "reason"):
        print e.reason()
    if hasattr(e, "headers"):
        print e.headers
    print "-"*60

class ParticipantHandler(object):
    """ ParticipantHandler object as defined by SkyNet API """ 

    def __init__(self):
        self.bzs = None

    def handle_lifecycle_control(self, ctrl):
        """ Participant control function

            :param ctrl: The control object. If the message attribute is "start"
                         calls a function to parse the configuration and
                         retrieve a bugzilla authenitcation cookie which is kept
                         around for the lifetime of the script run
            :type ctrl: object

        """
        if ctrl.message == "start":
            self.setup_config(ctrl.config)
            # If there are any auth errors in the config, find out now.
            for bzconfig in self.bzs.values():
                bzconfig['interface'].login()

    def setup_config(self, config):
        """
        :param config: ConfigParser instance with the bugzilla configuration
        """
        supported_bzs = config.get("bugzilla", "bzs").split(",")
        self.bzs = {}

        for bz in supported_bzs:
            self.bzs[bz] = {}
            self.bzs[bz]['platforms'] = config.get(bz, 'platforms').split(',')
            self.bzs[bz]['regexp'] = config.get(bz, 'regexp')
            self.bzs[bz]['compiled_re'] = re.compile(config.get(bz, 'regexp'))
            self.bzs[bz]['method'] = config.get(bz, 'method')
            self.bzs[bz]['rest_slug'] = config.get(bz, 'rest_slug', None)
            self.bzs[bz]['server'] = config.get(bz, 'bugzilla_server')
            self.bzs[bz]['user'] = config.get(bz, 'bugzilla_user')
            self.bzs[bz]['password'] = config.get(bz, 'bugzilla_pwd')
            template = config.get(bz, 'comment_template')
            try:
                self.bzs[bz]['template'] = open(template).read()
            except:
                raise RuntimeError("Couldn't open %s" % template)

            method = self.bzs[bz]['method']
            if method == 'REST':
                self.bzs[bz]['interface'] = BugzillaREST(self.bzs[bz])
            elif method == 'XMLRPC':
                self.bzs[bz]['interface'] = BugzillaXMLRPC(self.bzs[bz])
            else:
                raise RuntimeError("Bugzilla method %s not implemented"
                                   % method)

    def handle_wi(self, wi):
        """Handle an incoming request for work as described in the workitem."""

        wi.result = False

        f = wi.fields

        if not f.msg:
            f.msg = []

        # Support both ev.actions and plain workitem
        if not f.ev or not f.ev.actions:
            if not f.relevant_changelog or not f.package:
                raise RuntimeError("Fields 'relevant_changelog' and 'package' "
                        "are mandatory when not handling a request")
            # Pack the flat workitem data bits into a fake actions array
            # so we can reuse the same code path
            actions = [{ "type": "submit",
                         "targetpackage" : f.package,
                         "relevant_changelog" : f.relevant_changelog }]
        else:
            actions = f.ev.actions


        # Platform is used if it is present. NOT mandatory
        platform = f.platform

        # At this point all checks have passed as we have not returned
        # Failure to handle a mentioned bug is not considered a
        # process failure
        wi.result = True

        # Now handle all bugs mentioned in changelogs
        if wi.params.comment or wi.params.template:
            for action in actions:
                package = action["targetpackage"]
                if "relevant_changelog" in action:
                    relchloge = action["relevant_changelog"]
                else:
                    continue

                # Prepare a hash to collect result data
                results = dict(
                    msg = f.msg,
                    bugnums = [],
                    cbugnums = [],
                    fbugnums = [],
                    )

                # Go through each bugzilla we support
                for (bugzillaname, bugzilla) in self.bzs.iteritems():
                    # if this tracker is used for this platform
                    if platform and platform not in bugzilla['platforms']:
                        continue

                    # And then for each changelog deal with each bug
                    # mentioned
                    bugs = []
                    f.bz = {} # Prepare bz data for the Templater
                    for chloge in relchloge:
                        for m in bugzilla['compiled_re'].finditer(chloge):
                            bugnum = m.group('key')
                            if bugnum not in bugs:
                                bugs.append(bugnum)
                                # Add this to the WI for the Templater
                                f.bz.current_changlog_entry=chloge
                                handle_mentioned_bug(bugzilla, bugnum, wi,
                                                     results)
                    del f.as_dict()['bz']
                # Report on bugs.
                f.bz.bugs = []
                f.bz.failed_bugs = []
                if results["cbugnums"]:
                    msg = "Handled bugs %s" % ", ".join(results["cbugnums"])
                    print msg
                    f.msg.append(msg)
                    f.bz.bugs=results["cbugnums"]
                if results["fbugnums"]:
                    msg = "Failed to properly deal with bugs %s" % ", ".join(results["fbugnums"])
                    print msg
                    f.msg.append(msg)
                    f.bz.failed_bugs=results["fbugnums"]
