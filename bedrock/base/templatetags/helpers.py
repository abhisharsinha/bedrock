# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import datetime
import logging
import urllib.parse

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.utils.encoding import smart_str

import jinja2
from django_jinja import library

from bedrock.base import waffle
from bedrock.utils import expand_locale_groups

from ..urlresolvers import reverse

CSS_TEMPLATE = '<link href="%s" rel="stylesheet" type="text/css" />'
JS_TEMPLATE = '<script type="text/javascript" src="%s" charset="utf-8"></script>'
log = logging.getLogger(__name__)


@library.global_function
@jinja2.contextfunction
def switch(cxt, name, locales=None):
    """A template helper that replaces waffle

    * All calls default to True when DEV setting is True (for the listed locales).
    * If the env var is explicitly false it will be false even when DEV = True.
    * Otherwise the call is False by default and True is a specific env var exists and is truthy.

    For example:

        {% if switch('dude-and-walter') %}

    would check for an environment variable called `SWITCH_DUDE_AND_WALTER`. The string from the
    `switch()` call is converted to uppercase and dashes replaced with underscores.

    If the `locales` argument is a list of locales then it will only check the switch in those
    locales, and return False otherwise. The `locales` argument could also contain a "locale group",
    which is a list of locales for a prefix (e.g. "en" expands to "en-US, en-GB").
    """
    if locales:
        if cxt["LANG"] not in expand_locale_groups(locales):
            return False

    return waffle.switch(name)


@library.global_function
def thisyear():
    """The current year."""
    return jinja2.Markup(datetime.date.today().year)


@library.global_function
def url(viewname, *args, **kwargs):
    """Helper for Django's ``reverse`` in templates."""
    return reverse(viewname, args=args, kwargs=kwargs)


@library.filter
def urlparams(url_, hash=None, **query):
    """Add a fragment and/or query paramaters to a URL.

    New query params will be appended to exising parameters, except duplicate
    names, which will be replaced.
    """
    url = urllib.parse.urlparse(url_)
    fragment = hash if hash is not None else url.fragment

    # Use dict(parse_qsl) so we don't get lists of values.
    q = url.query
    query_dict = dict(urllib.parse.parse_qsl(smart_str(q))) if q else {}
    query_dict.update((k, v) for k, v in query.items())

    query_string = _urlencode([(k, v) for k, v in query_dict.items() if v is not None])
    new = urllib.parse.ParseResult(url.scheme, url.netloc, url.path, url.params, query_string, fragment)
    return new.geturl()


def _urlencode(items):
    """A Unicode-safe URLencoder."""
    try:
        return urllib.parse.urlencode(items)
    except UnicodeEncodeError:
        return urllib.parse.urlencode([(k, smart_str(v)) for k, v in items])


@library.filter
def mailtoencode(txt):
    """Url encode a string using %20 for spaces."""
    if isinstance(txt, str):
        txt = txt.encode("utf-8")
    return urllib.parse.quote(txt)


@library.filter
def urlencode(txt):
    """Url encode a string using + for spaces."""
    if isinstance(txt, str):
        txt = txt.encode("utf-8")
    return urllib.parse.quote_plus(txt)


@library.global_function
def static(path):
    if settings.DEBUG and path.startswith("/"):
        raise ValueError("Static paths must not begin with a slash")

    try:
        return staticfiles_storage.url(path)
    except ValueError as e:
        log.warning(str(e))
        return path


@library.global_function
def js_bundle(name):
    """Include a JS bundle in the template.

    Bundles are defined in the "media/static-bundles.json" file.
    """
    path = "js/{}.js".format(name)
    path = staticfiles_storage.url(path)
    return jinja2.Markup(JS_TEMPLATE % path)


@library.global_function
def css_bundle(name):
    """Include a CSS bundle in the template.

    Bundles are defined in the "media/static-bundles.json" file.
    """
    path = "css/{}.css".format(name)
    path = staticfiles_storage.url(path)
    return jinja2.Markup(CSS_TEMPLATE % path)


@library.global_function
def alternate_url(path, locale):
    alt_paths = settings.ALT_CANONICAL_PATHS
    path = path.lstrip("/")
    if path in alt_paths and locale in alt_paths[path]:
        return alt_paths[path][locale]

    return None


@library.global_function
@jinja2.contextfunction
def get_donate_params(ctx):
    """Returns donation params for the current locale with an added key
    containing a list version of the preset donation amounts.

    :returns: dictionary of donation values, including list of amount presets
    """

    donate_params = settings.DONATE_PARAMS.get(ctx["LANG"], settings.DONATE_PARAMS["en-US"])

    # presets are stored as a string but we need a list for views
    donate_params["preset_list"] = donate_params["presets"].split(",")

    return donate_params
