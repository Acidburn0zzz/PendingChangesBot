# PendingChangesBot
Bot tries to automatically review changes using Flagged Revisions in Wikipedia using predefined rules and ORES. 

* Homepage: https://github.com/zache-fi/PendingChangesBot
* Wikiproject: https://fi.wikipedia.org/wiki/Wikiprojekti:ORES

### Rules for approval

Approve article edits if :
* ... edit was made by autopatrolled or autoreviewed user
* ... edit was interwikichange
* ... edit was made by bot
* ... edit was made by former bot
* ... edit was reverted
* ... edit was revert to reviewed version
* ... edit was patrolled
* ... edit has high ORES goodfaith scores

Missing rules
* ... no content from the edit is in the latest version

### Prerequisite

Install pywikibot:
```
$ git clone --recursive https://gerrit.wikimedia.org/r/pywikibot/core.git pywikibot-core
$ cd pywikibot-core
$ python generate_user_files.py
```

Running the script:
```
$ cd ..
$ git clone https://github.com/zache-fi/PendingChangesBot.git
$ python pywikibot-core/pwb.py PendingChangesBot/import_candidates.py -lang:fi -family:wikipedia -pendingchanges -simulate
```
### Parameters
-pendingchanges   Work on all NS0 articles where changes are pending

-unreviewedpages  Work on all NS0 articles which have never been reviewed using 
                  Flagged revision

-noformerbots     Do not autoreview former bots

-noores           Do not use scores from ORES for approval

-simulate         Do not login or do actual reviews

-daylimit:N       Do not review page if version to be reviewed is older than N days

-ores_goodfaith_true_min:n     Minimum value needed for ORES goodfaith true value
-ores_goodfaith_true_max:n     Maximum value needed for ORES goodfaith true value
-ores_goodfaith_false_min:n    Minimum value needed for ORES goodfaith false value
-ores_goodfaith_false_max:n    Maximum value needed for ORES goodfaith false value

### Examples

Review unreviewed articles without flooding the pending changes queue
```
$ python pywikibot-core/pwb.py PendingChangesBot/pendingchanges.py -lang:fi -family:wikipedia -unreviewedpages -daylimit:30
```
Change ORES review parameters
```
$ python pywikibot-core/pwb.py PendingChangesBot/pendingchanges.py -lang:fi -family:wikipedia -unreviewedpages -ores_goodfaith_true_min:0.9 -ores_goodfaith_false_max:0.1
```
Review a single file
```
$ python pywikibot-core/pwb.py PendingChangesBot/pendingchanges.py -lang:fi -family:wikipedia -file:New_York
```

### Tool labs support

Script will fetch data from Tool Labs in cases where there is no good way to get that data using mediawiki API.

* formerbots – historical bot users who doesn't have bot flag anymore
http://tools.wmflabs.org/fiwiki-tools/pendingchanges/?lang=uk&action=formerbots&family=wikipedia

* reverted – test if revision was reverted
http://tools.wmflabs.org/fiwiki-tools/pendingchanges/?lang=uk&action=reverted&family=wikipedia&rev_id=15556107

* revert – test if revision was revert to reviewed version
http://tools.wmflabs.org/fiwiki-tools/pendingchanges/?lang=uk&action=revert&family=wikipedia&rev_id=14304076



