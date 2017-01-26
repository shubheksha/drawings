"""Ghost Buster. Static site generator for Ghost.
Usage:
  buster.py setup [--gh-repo=<repo-url>] [--dir=<path>]
  buster.py generate [--domain=<local-address>] [--dir=<path>] [--github-id=<github-id>]
  buster.py preview [--dir=<path>]
  buster.py deploy [--dir=<path>]
  buster.py add-domain <domain-name> [--dir=<path>]
  buster.py (-h | --help)
  buster.py --version
Options:
  -h --help                 Show this screen.
  --version                 Show version.
  --dir=<path>              Absolute path of directory to store static pages.
  --domain=<local-address>  Address of local ghost installation [default: localhost:2368].
  --github-id=<github-id>   Your Github ID for http://github-id.github.io URL
  --gh-repo=<repo-url>      URL of your gh-pages repository.
"""

import os
import re
import sys
import fnmatch
import shutil
import SocketServer
import SimpleHTTPServer
from docopt import docopt
from time import gmtime, strftime
from git import Repo
from pyquery import PyQuery

from HTMLParser import HTMLParser
import urllib2
import sys

def cleanupString(string):
    string = urllib2.unquote(string).decode('utf8')
    return HTMLParser().unescape(string).encode(sys.getfilesystemencoding())


def main():
    arguments = docopt(__doc__, version='0.1.3')
    if arguments['--dir'] is not None:
        static_path = arguments['--dir']
    else:
        static_path = os.path.join(os.getcwd(), 'static')

    if arguments['--github-id'] is not None:
        github_url = "{}.github.io".format(arguments['--github-id'])
    else:
        github_url = None

    if arguments['generate']:
        command = ("wget "
                   "--level=0 "               # set level to infinitive
                   "--recursive "             # follow links to download entire site
                   "--convert-links "         # make links relative
                   "--page-requisites "       # grab everything: css / inlined images
                   "--no-parent "             # don't go to parent level
                   "--directory-prefix {1} "  # download contents to static/ folder
                   "--no-host-directories "   # don't create domain named folder
                   "--restrict-file-name=unix "  # don't escape query string
                   "{0}").format(arguments['--domain'], static_path)
        os.system(command)

        # copy sitemap files since Ghost 0.5.7
        # from https://github.com/joshgerdes/buster/blob/f28bb10fc9522b8b1b1a74d8b74865562d9d5f9e/buster/buster.py
        base_command = "wget --convert-links --page-requisites --no-parent --directory-prefix {1} --no-host-directories --restrict-file-name=unix {0}/{2}"
        command = base_command.format(arguments['--domain'], static_path, "sitemap.xsl")
        os.system(command)
        command = base_command.format(arguments['--domain'], static_path, "sitemap.xml")
        os.system(command)
        command = base_command.format(arguments['--domain'], static_path, "sitemap-pages.xml")
        os.system(command)
        command = base_command.format(arguments['--domain'], static_path, "sitemap-posts.xml")
        os.system(command)
        command = base_command.format(arguments['--domain'], static_path, "sitemap-authors.xml")
        os.system(command)
        command = base_command.format(arguments['--domain'], static_path, "sitemap-tags.xml")
        os.system(command)

        # copy static pages
        # about page
        command = base_command.format(arguments['--domain'], static_path, "/about/")
        os.system(command)
        # rss page
        command = base_command.format(arguments['--domain'], static_path, "/rss/")
        os.system(command)


        # remove query string since Ghost 0.4
        file_regex = re.compile(r'.*?(\?.*)')
        for root, dirs, filenames in os.walk(static_path):
            for filename in filenames:
                if file_regex.match(filename):
                    newname = re.sub(r'\?.*', '', filename)
                    print "Rename", filename, "=>", newname
                    os.rename(os.path.join(root, filename), os.path.join(root, newname))

        # remove superfluous "index.html" from relative hyperlinks found in text
        abs_url_regex = re.compile(r'^(?:[a-z]+:)?//', flags=re.IGNORECASE)

        def fixLinks(text, parser):
            d = PyQuery(bytes(bytearray(text, encoding='utf-8')), parser=parser)
            for element in d('a, link'):
                e = PyQuery(element)
                href = e.attr('href')

                if href is None:
                    continue
                if (not abs_url_regex.search(href)) or ('/rss/' in href):
                    new_href = re.sub(r'rss/$', 'feed.rss', href)
                    new_href = re.sub(r'index\.html$', '', new_href)
                    new_href = re.sub(r'index\.html\#$', '', new_href)
                    e.attr('href', new_href)
                    print "\t", href, "=>", new_href
            if parser == 'html':
                return "<!DOCTYPE html>\n<html>" + d.html(method='html').encode('utf8') + "</html>"
            elif parser == 'xml':
                return "<?xml version=\"1.0\" encoding=\"UTF-8\"?>" + d.__unicode__().encode('utf8')
            return "<!DOCTYPE html>\n<html>" + d.__unicode__().encode('utf8') + "</html>"

        # fix links in all html files
        for root, dirs, filenames in os.walk(static_path):
            for filename in fnmatch.filter(filenames, "*.html"):
                filepath = os.path.join(root, filename)
                parser = 'html'
                if root.endswith("/rss"):  # rename rss index.html to feed.rss
                    parser = 'xml'
                    newfilepath = os.path.join(root, os.path.splitext('feed')[0] + ".rss")
                    os.rename(filepath, newfilepath)
                    filepath = newfilepath
                with open(filepath) as f:
                    filetext = f.read().decode('utf8')
                print "fixing links in ", filepath
                newtext = fixLinks(filetext, parser)
                with open(filepath, 'w') as f:
                    f.write(newtext)

        def trans_local_domain_to_github_pages(text):
            modified_text = text.replace('localhost:2368', 'shubheksha.com/drawings')
            #modified_text = re.sub(r"localhost:2368", "shubheksha.com/drawings", text)
            #modified_text = re.sub(r"127.0.0.1:2368", "shubheksha.com/drawings", text)
            return modified_text

        def fix_font_tags(text):
            modified_text = re.sub(r"http://fonts.googleapis.com", "https://fonts.googleapis.com", text)
            return modified_text

        def fix_gravatar_tags(text):
            modified_text = re.sub(r"http://www.gravatar.com/avatar/", "https://www.gravatar.com/avatar/", text)
            return modified_text

        def remove_v_tag_in_css_and_html(text):
            modified_text = re.sub(r"%3Fv=[\d|\w]+\.css", "", text)
            modified_text = re.sub(r".js%3Fv=[\d|\w]+", ".js", modified_text)
            modified_text = re.sub(r".woff%3Fv=[\d|\w]+", ".woff", modified_text)
            modified_text = re.sub(r".ttf%3Fv=[\d|\w]+", ".ttf", modified_text)
            modified_text = re.sub(r".svg%3Fv=[\d|\w]+", ".svg", modified_text)

            modified_text = re.sub(r"js\.html", "js", modified_text)
            modified_text = re.sub(r"css\.html", "css", modified_text)
            modified_text = re.sub(r"png\.html", "png", modified_text)
            modified_text = re.sub(r"jpg\.html", "jpg", modified_text)

            modified_text = re.sub(r"eot\.html", "eot", modified_text)
            modified_text = re.sub(r"woff\.html", "woff", modified_text)
            modified_text = re.sub(r"ttf\.html", "ttf", modified_text)
            modified_text = re.sub(r"svg\.html", "svg", modified_text)
            modified_text = re.sub(r"\?v=1\.html", "", modified_text)

            return modified_text

        for root, dirs, filenames in os.walk(static_path):
            for filename in filenames:
                if filename.endswith(('.html', '.xml', '.css', '.xsl', '.rss', '.txt', '.js')):
                    filepath = os.path.join(root, filename)
                    with open(filepath) as f:
                        filetext = f.read()
                    print "fixing local domain in ", filepath
                    newtext = trans_local_domain_to_github_pages(filetext)
                    newtext = remove_v_tag_in_css_and_html(newtext)
                    newtext = fix_font_tags(newtext)
                    newtext = fix_gravatar_tags(newtext)
                    newtext = cleanupString(newtext)
                    with open(filepath, 'w') as f:
                        f.write(newtext)

        # Rename rss feed from /rss/feed.rss to /feed.rss for GH Pages.
        os.rename(os.path.join(static_path, 'rss/feed.rss'), os.path.join(static_path, 'feed.rss'))
        os.rmdir(os.path.join(static_path, 'rss'))

    elif arguments['preview']:
        os.chdir(static_path)

        Handler = SimpleHTTPServer.SimpleHTTPRequestHandler
        httpd = SocketServer.TCPServer(("", 9000), Handler)

        print "Serving at port 9000"
        # gracefully handle interrupt here
        httpd.serve_forever()

    elif arguments['setup']:
        if arguments['--gh-repo']:
            repo_url = arguments['--gh-repo']
        else:
            repo_url = raw_input("Enter the Github repository URL:\n").strip()

        # Create a fresh new static files directory
        if os.path.isdir(static_path):
            confirm = raw_input("This will destroy everything inside static/."
                                " Are you sure you want to continue? (y/N)").strip()
            if confirm != 'y' and confirm != 'Y':
                sys.exit(0)
            shutil.rmtree(static_path)

        # User/Organization page -> master branch
        # Project page -> gh-pages branch
        branch = 'gh-pages'
        regex = re.compile(".*[\w-]+\.github\.(?:io|com).*")
        if regex.match(repo_url):
            branch = 'master'

        # Prepare git repository
        repo = Repo.init(static_path)
        git = repo.git

        if branch == 'gh-pages':
            git.checkout(b='gh-pages')
        repo.create_remote('origin', repo_url)

        # Add README
        file_path = os.path.join(static_path, 'README.md')
        with open(file_path, 'w') as f:
            f.write('# Blog\nPowered by [Ghost](http://ghost.org) and [Buster](https://github.com/axitkhurana/buster/).\n')

        print "All set! You can generate and deploy now."

    elif arguments['deploy']:
        repo = Repo(static_path)
        repo.git.add('.')

        current_time = strftime("%Y-%m-%d %H:%M:%S", gmtime())
        repo.index.commit('Gremlin activity detected at {}'.format(current_time))

        origin = repo.remotes.origin
        repo.git.execute(['git', 'push', '-u', origin.name,
                         repo.active_branch.name])
        print "Good job! Deployed to Github Pages."

    elif arguments['add-domain']:
        repo = Repo(static_path)
        custom_domain = arguments['<domain-name>']

        file_path = os.path.join(static_path, 'CNAME')
        with open(file_path, 'w') as f:
            f.write(custom_domain + '\n')

        print "Added CNAME file to repo. Use `deploy` to deploy"

    else:
        print __doc__

if __name__ == '__main__':
    main()
