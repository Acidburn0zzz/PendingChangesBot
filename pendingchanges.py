#!/usr/bin/python
# -*- coding: utf-8  -*-
"""
Script for doing the automatic flagged review reviews

These command line parameters can be used to specify which pages to work on:

&params;

-pendingchanges   Work on all NS0 articles where changes are pending

-unreviewedpages  Work on all NS0 articles which have never been reviewed using 
                  Flagged revision

-noformerbots     Do not autoreview former bots

-noores           Do not use scores from ORES for approval

-daylimit:N       Do not review page if the version that is being reviewed is older than N days

-ores_goodfaith_true_min:n     Minimum value needed for ORES goodfaith true value
-ores_goodfaith_true_max:n     Maximum value needed for ORES goodfaith true value
-ores_goodfaith_false_min:n    Minimum value needed for ORES goodfaith false value
-ores_goodfaith_false_max:n    Maximum value needed for ORES goodfaith false value

Example:

       python pwb.py PendingChangesBot/pendingchanges.py -lang:fi -family:wikipedia -pendingchanges -simulate

       python pwb.py PendingChangesBot/pendingchanges.py -lang:fi -family:wikipedia -pendingchanges

       python pwb.py PendingChangesBot/pendingchanges.py -lang:fi -family:wikipedia -unreviewedpages -daylimit:30

       python pwb.py PendingChangesBot/pendingchanges.py -lang:fi -family:wikipedia -unreviewedpages -ores_goodfaith_true_min:0.9 -ores_goodfaith_false_max:0.1


"""
#
# (C) 2017 Kimmo Virtanen, <zache.fiwiki@gmail.com>
#
# Distributed under the terms of the MIT license.
#
from __future__ import absolute_import, unicode_literals

import sys
import re
import json
import pywikibot
from pywikibot import User
from pywikibot import config
from pywikibot import i18n
from pywikibot import pagegenerators
from pywikibot.data import api
from pywikibot.comms import http
from urllib import quote
import dateutil.parser
import datetime
import time
# This is required for the text that is shown when you run this script
# with the parameter -help.
docuReplacements = {
    '&params;': pagegenerators.parameterHelp,
}

class PendingChangesRobot(object):

    def __init__(self, generator, oresconfig=None, daylimit=None, useformerbots=1):
        """Constructor."""
        self.generator = generator
        self.simulateMode = pywikibot.config.simulate
        self.autoreviewedusers = {}
        self.botusers = {}
        self.formerbotusers = {}
        self.oressiteinfo=self.get_ores_siteinfo()
        self.oresconfig = oresconfig
        self.daylimit = daylimit
        self.useformerbots=useformerbots

        # Page cache
        self._patrolledrevs=None
        self._oresrevs=None

    def reset_pagecache(self):
        self._patrolledrevs=None
        self._oresrevs=None


    def get_autoreviewedusers(self):
        users_gen = api.ListGenerator(listaction="allusers", site=pywikibot.Site(), aurights='autoreview|autopatrol')
        userlist = {ul['name']:ul for ul in users_gen}
        return userlist

    def get_botusers(self):
        site=pywikibot.Site()
        userlist = {ul['name']:ul for ul in site.botusers()}
        return userlist

    def get_formerbotusers(self):
        site=pywikibot.Site()
        url=('http://tools.wmflabs.org/fiwiki-tools/pendingchanges/?action=formerbots&family=wikipedia&lang=%s' % site.lang)

        try:
            file=http.fetch(url)
        except:
            pywikibot.error("Reading %s failed",  url)
        data = json.loads(file.decode("utf-8"))
        userlist={name:1 for name in data["formerbots"]}
        
        return userlist

    def test_reverted(self, page, rev_id, action):
        site=pywikibot.Site()
        url=('http://tools.wmflabs.org/fiwiki-tools/pendingchanges/?lang=%s&action=%s&family=wikipedia&rev_id=%d' % (site.lang, action, rev_id))
        try:
            file=http.fetch(url)
        except:
            pywikibot.error("Reading %s failed",  url)

        data = json.loads(file.decode("utf-8"))        
        if (str(rev_id) in data[action] 
           and  data[action][str(rev_id)] == True):
           return 1

        return 0

    def get_ores_siteinfo(self):
        site=pywikibot.Site()
        sitename=('%swiki' % site.lang)

        url=('https://ores.wmflabs.org/v2/scores/%s' % sitename)
        file=http.fetch(url)
        data = json.loads(file.decode("utf-8"))

        if "scores" in data:
           if sitename in data["scores"]:
              return data["scores"][sitename]

        return None
       
    def get_oresrevs(self, rev_ids=[]):
        if self._oresrevs==None:
           site=pywikibot.Site()
           url=('https://ores.wikimedia.org/scores/%swiki?models=damaging|reverted|goodfaith&revids=' % site.lang)
           url=url + "|".join(str(key)  for key in rev_ids[:40])

           try:
              file=http.fetch(url)
           except:
              pywikibot.error("Reading %s failed", url)
              time.sleep(10)
              file=http.fetch(url)
           data = json.loads(file.decode("utf-8"))
           self._oresrevs=data
        return self._oresrevs

    def test_oresrevs(self, rev_id, revlist, model):
        if not model in self.oressiteinfo:
           return False

        if not self.oresconfig:
           return False

        if not model in self.oresconfig:
           return False  

        settings=self.oresconfig[model]
        oresrevs=self.get_oresrevs(revlist)

        if str(rev_id) in oresrevs:
           ores_rev=oresrevs[str(rev_id)]
           if model in ores_rev:
              scorer=ores_rev[model]["probability"]
              if (float(scorer["true"]) >= settings["true"]["min"]
                 and float(scorer["true"]) <= settings["true"]["max"]
                 and float(scorer["false"]) <= settings["false"]["max"]
                 and float(scorer["false"]) >= settings["false"]["min"] ) :
                 return True
        return False

    def get_patrolledrevs(self, page, offset_time):
        site=pywikibot.Site()
        if self._patrolledrevs==None:
           log_gen=site.logevents(logtype="patrol", page=page, end=offset_time)
	   self._patrolledrevs = [entry.current_id for entry in log_gen]
        return self._patrolledrevs

    def test_patrolledrevs(self, page, rev_id, fp_pending_since):
        patrolledrevs=self.get_patrolledrevs(page.title(), fp_pending_since);
        if rev_id in patrolledrevs:
            return 1
        else:
            return 0

    def wordtest(self, parenttext, oldrevtext, latesttext):
        oldrevwords = set(re.split(r"\s+",oldrevtext))
        parentwords = set(re.split(r"\s+",parenttext))
        latestwords = set(re.split(r"\s+",latesttext))
        addedwords  = []
        removedwords= []
        existingwords= []

        for word in oldrevwords:
            if word not in parentwords:
               addedwords.append(word)

        for word in parentwords:
            if word not in oldrevwords:
               removedwords.append(word)

        for word in addedwords:
            if word in latestwords:
               existingwords.append(word)

        if (len(addedwords) == 0 and len(removedwords)==0):
            return 1
        elif (len(existingwords)>0):
            return 2
        else:
            return 0

    def remove_interwiki(self, str):
        iwlist="(aa|ab|ace|ady|af|ak|als|am|an|ang|ar|arc|arz|as|ast|av|ay|az|azb|ba|bar|bat-smg|bcl|be|be-tarask|bg|bh|bi|bjn|bm|bn|bo|bpy|br|bs|bug|bxr|ca|cbk-zam|cdo|ce|ceb|ch|cho|chr|chy|ckb|co|cr|crh|cs|csb|cu|cv|cy|da|de|diq|dsb|dty|dv|dz|ee|el|eml|en|eo|es|et|eu|ext|fa|ff|fi|fiu-vro|fj|fo|fr|frp|frr|fur|fy|ga|gag|gan|gd|gl|glk|gn|gom|got|gu|gv|ha|hak|haw|he|hi|hif|ho|hr|hsb|ht|hu|hy|hz|ia|id|ie|ig|ii|ik|ilo|io|is|it|iu|ja|jam|jbo|jv|ka|kaa|kab|kbd|kg|ki|kj|kk|kl|km|kn|ko|koi|kr|krc|ks|ksh|ku|kv|kw|ky|la|lad|lb|lbe|lez|lg|li|lij|lmo|ln|lo|lrc|lt|ltg|lv|mai|map-bms|mdf|mg|mh|mhr|mi|min|mk|ml|mn|mo|mr|mrj|ms|mt|mus|mwl|my|myv|mzn|na|nah|nap|nds|nds-nl|ne|new|ng|nl|nn|no|nov|nrm|nso|nv|ny|oc|olo|om|or|os|pa|pag|pam|pap|pcd|pdc|pfl|pi|pih|pl|pms|pnb|pnt|ps|pt|qu|rm|rmy|rn|ro|roa-rup|roa-tara|ru|rue|rw|sa|sah|sc|scn|sco|sd|se|sg|sh|si|simple|sk|sl|sm|sn|so|sq|sr|srn|ss|st|stq|su|sv|sw|szl|ta|tcy|te|tet|tg|th|ti|tk|tl|tn|to|tpi|tr|ts|tt|tum|tw|ty|tyv|udm|ug|uk|ur|uz|ve|vec|vep|vi|vls|vo|wa|war|wo|wuu|xal|xh|xmf|yi|yo|za|zea|zh|zh-classical|zh-min-nan|zh-yue|zu)";
        return re.sub("\[\[" + iwlist + ":[^\]\n]*?\]\]", "", str).strip()

    def test_content(self, page, rev_id, rev_parent_id):
        latesttext=page.get(get_redirect=True)
        oldrevtext=page.getOldVersion(rev_id)

        # First revision
        if rev_parent_id == 0 :
           parenttext=""
        else:
           parenttext=page.getOldVersion(int(rev_parent_id))

        if latesttext == None:
           return False

        if oldrevtext == None:
           return False

        if parenttext == None:
           return False

        # Basic cleanup
        latesttext=latesttext.lower().strip()
        oldrevtext=oldrevtext.lower().strip()
        parenttext=parenttext.lower().strip()

        # Revisions are identical
        if oldrevtext==parenttext:
           return "nochange"

        # Remove interwiki links (mostly good and moved to wikidata)
        parenttext=self.remove_interwiki(parenttext)
        oldrevtext=self.remove_interwiki(oldrevtext)

        if oldrevtext==parenttext:
           return "interwiki"

        # Split text to words and check what was added or removed
        testresult=self.wordtest(parenttext, oldrevtext, latesttext);
        if testresult == 1:
           return "wordtest1"

        # Remove special characters
        wikicleanup="[\[\]\{\}\|.,:;'\"<>()\-–*]+"
        oldrevtext=re.sub(wikicleanup, " ", oldrevtext).strip()
        parenttext=re.sub(wikicleanup, " ", parenttext).strip()
        latesttext=re.sub(wikicleanup, " ", latesttext).strip()

        # Split text to words and check what was added or removed
        testresult=self.wordtest(parenttext, oldrevtext, latesttext);
        if testresult == 2:
           return "wordtest2"
        else:
           return ""

    def review(self, rev_id, comment):
           if self.simulateMode:
              return True

           site=pywikibot.Site()
           edittoken = site.tokens['edit']
           parameters={'action':'review', 'revid':rev_id, 'flag_accuracy': 1, 'token': edittoken, 'comment': comment}

           try:
              req = api.Request(site=site, parameters=parameters)
              req.submit()
           except api.APIError as e:
              pywikibot.error("There was an API error when reviewing the edit: %s" % json.dumps(self.simulateMode))
              return False
           else:
              return True

    def flaggedinfo(self, page):
        site=pywikibot.Site()
        url=(u'https://%s.%s.org/w/api.php?format=json&action=query&prop=info|flagged&pageids=%d' % (site.lang, site.family, page.pageid))

        file=http.fetch(url)
        data = json.loads(file.decode("utf-8"))

        if data["query"] and data["query"]["pages"]:
           pageid=str(page.pageid)
           if pageid in data["query"]["pages"]:
               return data["query"]["pages"][pageid]
           else:
               pywikibot.error("Flaggedinfo error. Page not found.")
               exit(1)

        return {}

    def login(self):
        if self.simulateMode:
           return True

        site=pywikibot.Site()
        site.login()
        return site.logged_in()

    def create_comment(self, approves):
        users=set()
        rules=set()
        revs=set()
        for row in approves:
           users.add(row["rev"]["user"])
           revs.add(row["rev"]["revid"])
           rules.add(row["approve_reason"])

        rev_plural= 'revisions' if len(revs)>1 else 'revision'
        user_plural= 'users' if len(users)>1 else 'user'
        rule_plural= 'rules' if len(rules)>1 else 'rule'

        rev_delim= ' and ' if len(revs)==2 else ', '
        user_delim= u' and ' if len(users)==2 else u', '
        rule_delim= u' and ' if len(rules)==2 else u', '

        revs_str= rev_delim.join(str(key)  for key in revs)
        users_str= user_delim.join(key.encode('utf-8').strip()  for key in users)
        rules_str= rule_delim.join(key.encode('utf-8').strip()  for key in rules)

        vars=(rev_plural, revs_str, user_plural, users_str, rule_plural, rules_str)
        comment=("Approved %s %s from %s %s using %s %s" % vars)

        # If the comment is too long then make a shorter one
        if (len(comment)>150):
           vars=(rev_plural, revs_str, rule_plural, rules_str)
           comment=("Approved %s %s using %s %s" % vars)

        # If the comment is still too long then make a shorter one
        if (len(comment)>150):
           vars=(len(revs), rev_plural, rule_plural, rules_str)
           comment=("Approved %d %s using %s %s" % vars)

        # If the comment is for a single edit then add more info
	if (len(revs)==1 and "ores" in rules):
           oresrevs=self.get_oresrevs()
           goodfaith_true=oresrevs[str(list(revs)[0])]["goodfaith"]["probability"]["true"]
           goodfaith_false=oresrevs[str(list(revs)[0])]["goodfaith"]["probability"]["false"]

           comment+=(' goodfaith (t/f: %.2f/%.2f)' % (goodfaith_true, goodfaith_false))

        return comment



    def treat(self, page):
        pywikibot.output(u'\n>>> %s <<<' % page.title())
        self.reset_pagecache()

        if not page.exists():
            return True

        if page.namespace() != 0:
           return True

        site = page.site
        flaggedinfo=self.flaggedinfo(page)
        oresconfig=self.oresconfig

        if "flagged" in flaggedinfo:
           if "pending_since" in flaggedinfo["flagged"]:
               pending_since=dateutil.parser.parse(flaggedinfo["flagged"]["pending_since"])
           else:
               # Already reviewed
               return True
        else:
           pending_since=None

        rev_gen = page.revisions(reverse=True, starttime=pending_since, content=False)
        revlist=[]
        for rev in rev_gen:
           if (rev["user"] not in self.botusers and rev["user"] not in self.autoreviewdusers):
              revlist.append(int(rev["revid"]))

        # reset revision generator
        rev_gen = page.revisions(reverse=True, starttime=pending_since, content=False)

        latest_ok=0
        latest_timestamp=None
        approves=[]

        for rev in rev_gen:
           approve_reason=""
           rev_id=int(rev["revid"])
           rev_user=rev["user"]
           rev_timestamp=rev["timestamp"]
           rev_parent_id=rev.parent_id

           if rev_user in self.botusers:
              approve_reason="bot"
              latest_ok=rev_id
           elif rev_user in self.autoreviewdusers :
              approve_reason="autoreview"
              latest_ok=rev_id
           elif rev_user in self.formerbotusers :
              approve_reason="formerbot"
              latest_ok=rev_id
           elif self.test_patrolledrevs(page, rev_id, pending_since):
              approve_reason="patrolled"
              latest_ok=rev_id
           elif self.test_reverted(page, rev_id, "reverted"):
              approve_reason="reverted"
              latest_ok=rev_id
           elif self.test_reverted(page, rev_id, "revert"):
              approve_reason="revert"
              latest_ok=rev_id
           elif self.test_oresrevs(rev_id, revlist, "goodfaith"):
              approve_reason="ores"
              latest_ok=rev_id
           else:

              # Try to figure out what to do using diff
              test_result=self.test_content(page, rev_id, rev_parent_id)

              if test_result=="nochange":
                   approve_reason="nochange"
                   latest_ok=rev_id
              elif test_result=="interwiki":
                   approve_reason="interwiki"
                   latest_ok=rev_id

           state='OK' if approve_reason!="" else 'NOT OK'
           pywikibot.output(u'%s\t%s Revision %d %s %s' % (state, "{:<15}".format(approve_reason), rev_id, rev_timestamp, rev_user))

           if approve_reason != "":
              latest_ok=rev_id
              latest_timestamp=rev_timestamp
              row={ 'rev':rev, 'approve_reason':approve_reason}
              approves.append(row)
           else:
              break

        if latest_ok :
           pywikibot.output(u'Latest ok revision: %d' % latest_ok)           
           if (page.latest_revision_id != latest_ok 
              and self.daylimit 
              and datetime.datetime.now() > (latest_timestamp + datetime.timedelta(days=self.daylimit))):
                  pywikibot.output(u'Skipping review of revision: %d because it is older than %d days."' % (latest_ok,self.daylimit))              
           elif self.login():
              comment=self.create_comment(approves)
              result=self.review(rev_id=latest_ok, comment=comment)
              if result:
                 if self.simulateMode:
                     pywikibot.output('Reviewed (simulated) revision: %d with comment: "%s"' % (latest_ok,comment))
                 else:
                     pywikibot.output('Reviewed revision: %d with comment: "%s"' % (latest_ok,comment))


    def run(self):
        site=pywikibot.Site()
        pywikibot.output(u'Family: %s ; Lang %s' % (site.family, site.lang) )
        pywikibot.output(u'Ores config: %s' % json.dumps(self.oresconfig) )

        self.autoreviewdusers=self.get_autoreviewedusers()
        self.botusers=self.get_botusers()
        if self.useformerbots:
            self.formerbotusers=self.get_formerbotusers()

        """Check each page passed."""
        for page in self.generator:
            self.treat(page)


def unreviewdpagesGenerator():
    site = pywikibot.Site()
    list_gen = api.ListGenerator(listaction="unreviewedpages", site=site,  urlimit=5, urnamespace=0, urfilterredir="nonredirects" )

    for entry in list_gen:
        page=pywikibot.Page(site, entry["title"])
        yield page

def pendingchangesGenerator():
    site = pywikibot.Site()
    list_gen = api.ListGenerator(listaction="oldreviewedpages", site=site,  orlimit=5, ornamespace=0 )

    for entry in list_gen:
        page=pywikibot.Page(site, entry["title"])
        yield page

def main(*args):
    """
    Process command line arguments and invoke bot.

    """

    # Force utf8. Why is this needed? (FIXME)
    reload(sys)  
    sys.setdefaultencoding('utf8')

    # Don't approve the edit if it's older than N days
    daylimit=None

    # Page generator
    gen = None

    # This factory is responsible for processing command line arguments
    # that are also used by other scripts and that determine on which pages
    # to work on.
    genFactory = pagegenerators.GeneratorFactory()


    #Default values for ORES
    oresconfig={
        'goodfaith' : { 
           'true':  { 'min': 0.85, 'max':1 },
           'false': { 'min': 0, 'max':0.15 }
       }
    }

    # Autoreview former bots
    formerbots=1

    for arg in pywikibot.handle_args(args):
        ores_arg=re.search('ores_(.*?)_(true|false)_(min|max):([0-9.]*?)$', arg)

        if arg == '-pendingchanges':
            gen = pendingchangesGenerator()
        elif arg == '-unreviewedpages':
            gen = unreviewdpagesGenerator()
        elif arg == '-noores':
            oresconfig=None
        elif arg == '-noformerbots':
            formerbots=0
        elif arg.startswith('-daylimit:'):
            try:
                daylimit=int(arg[10:])
            except:
                pywikibot.error("Unsupported daylimit value")
        elif ores_arg:
           # Ores config. Syntax is ores_SCORER_true/false_min/max:float
           # Example: -ores_goodfaith_true_min:0.5
           m = ores_arg.groups()
           if m[0] in oresconfig:
              try:
                 oresconfig[m[0]][m[1]][m[2]]=float(m[3])
              except:
                 pywikibot.error("Unsupported ORES value in key %s" % arg)
           else:
              pywikibot.error("Unsupported ORES key %s" % arg)
        else:
            genFactory.handleArg(arg)

    if gen==None:
        gen = genFactory.getCombinedGenerator()

    if gen:
        preloadingGen = pagegenerators.PreloadingGenerator(gen)
        bot = PendingChangesRobot(preloadingGen, oresconfig, daylimit, formerbots)
        bot.run()
    else:
        pywikibot.showHelp('pendingchanges')

if __name__ == "__main__":
    main()
