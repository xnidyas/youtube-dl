# coding: utf-8
from __future__ import unicode_literals

import re
import js2py

from .common import InfoExtractor
from ..compat import compat_chr
from ..utils import (
    determine_ext,
    ExtractorError,
)

class DecodeError(Exception):
    pass


class OpenloadIE(InfoExtractor):
    _VALID_URL = r'https?://(?:openload\.(?:co|io)|oload\.tv)/(?:f|embed)/(?P<id>[a-zA-Z0-9-_]+)'

    _TESTS = [{
        'url': 'https://openload.co/f/kUEfGclsU9o',
        'md5': 'bf1c059b004ebc7a256f89408e65c36e',
        'info_dict': {
            'id': 'kUEfGclsU9o',
            'ext': 'mp4',
            'title': 'skyrim_no-audio_1080.mp4',
            'thumbnail': r're:^https?://.*\.jpg$',
        },
    }, {
        'url': 'https://openload.co/embed/rjC09fkPLYs',
        'info_dict': {
            'id': 'rjC09fkPLYs',
            'ext': 'mp4',
            'title': 'movie.mp4',
            'thumbnail': r're:^https?://.*\.jpg$',
            'subtitles': {
                'en': [{
                    'ext': 'vtt',
                }],
            },
        },
        'params': {
            'skip_download': True,  # test subtitles only
        },
    }, {
        'url': 'https://openload.co/embed/kUEfGclsU9o/skyrim_no-audio_1080.mp4',
        'only_matching': True,
    }, {
        'url': 'https://openload.io/f/ZAn6oz-VZGE/',
        'only_matching': True,
    }, {
        'url': 'https://openload.co/f/_-ztPaZtMhM/',
        'only_matching': True,
    }, {
        # unavailable via https://openload.co/f/Sxz5sADo82g/, different layout
        # for title and ext
        'url': 'https://openload.co/embed/Sxz5sADo82g/',
        'only_matching': True,
    }, {
        'url': 'https://oload.tv/embed/KnG-kKZdcfY/',
        'only_matching': True,
    }]
    
    _API_URL = 'https://api.openload.co/1'
    _PAIR_INFO_URL = _API_URL + '/streaming/info'
    _GET_VIDEO_URL = _API_URL + '/streaming/get?file=%s'

    @staticmethod
    def _extract_urls(webpage):
        return re.findall(
            r'<iframe[^>]+src=["\']((?:https?://)?(?:openload\.(?:co|io)|oload\.tv)/embed/[a-zA-Z0-9-_]+)',
            webpage)

    def _eval_id_decoding(self, webpage, ol_id):
        try:
            # raise # uncomment to test method with pairing
            js_code = self._search_regex(
                r"(ﾟωﾟﾉ=.*?\('_'\);.*?)ﾟωﾟﾉ= /｀ｍ´）ﾉ ~┻━┻   //\*´∇｀\*/ \['_'\];",
                webpage, 'openload decrypt code', flags=re.S)
            js_code = re.sub('''if\s*\([^\}]+?typeof[^\}]+?\}''', '', js_code)
        except ExtractorError:
            raise DecodeError('Could not find JavaScript')

        js_code = '''
            var id = "%s"
              , decoded
              , document = {}
              , window = this
              , $ = function(){
                  return {
                    text: function(a){
                      if(a)
                        decoded = a;
                      else
                        return id;
                    },
                    ready: function(a){
                      a()
                    }
                  }
                };
            (function(d){
              var f = function(){};
              var s = '';
              var o = null;
              ['close','createAttribute','createDocumentFragment','createElement','createElementNS','createEvent','createNSResolver','createRange','createTextNode','createTreeWalker','evaluate','execCommand','getElementById','getElementsByName','getElementsByTagName','importNode','open','queryCommandEnabled','queryCommandIndeterm','queryCommandState','queryCommandValue','write','writeln'].forEach(function(e){d[e]=f;});
              ['anchors','applets','body','defaultView','doctype','documentElement','embeds','firstChild','forms','images','implementation','links','location','plugins','styleSheets'].forEach(function(e){d[e]=o;});
              ['URL','characterSet','compatMode','contentType','cookie','designMode','domain','lastModified','referrer','title'].forEach(function(e){d[e]=s;});
            })(document);
            %s;
            decoded;''' % (ol_id, js_code)

        try:
            decoded = js2py.eval_js(js_code)
            if ' ' in decoded or decoded == '':
                raise
            return decoded
        except:
            raise DecodeError('Could not eval ID decoding')

    def _pairing_method(self, video_id):
        get_info = self._download_json(self._GET_VIDEO_URL % video_id, video_id)
        status = get_info.get('status')
        if status == 200:
            result = get_info.get('result', {})
            return result.get('name'), result.get('url')
        elif status == 403:
            pair_info = self._download_json(self._PAIR_INFO_URL, video_id,
                                            note='Downloading pairing info')
            if pair_info.get('status') == 200:
                pair_url = pair_info.get('result', {}).get('auth_url')
                if pair_url:
                    raise ExtractorError('Open this url: %s, solve captcha, click "Pair" button and try again'
                                         % pair_url, expected=True, video_id=video_id)
                else:
                    raise ExtractorError('Pair URL not found', video_id=video_id)
            else:
                raise ExtractorError('Error loading pair info', video_id=video_id)
        else:
            raise ExtractorError('Error loading JSON metadata', video_id=video_id)

    def _real_extract(self, url):
        title = None
        video_id = self._match_id(url)
        webpage = self._download_webpage('https://openload.co/embed/%s/' % video_id, video_id)

        if 'File not found' in webpage or 'deleted by the owner' in webpage:
            raise ExtractorError('File not found', expected=True, video_id=video_id)

        ol_id = self._search_regex(
            r'''<span[^>]+id=(["'])[^"']+\1[^>]*>(?P<id>[0-9A-Za-z]+)</span>''',
            webpage, 'openload ID', fatal=False, group='id')
        video_url = 'https://openload.co/stream/%s?mime=true'
        try:
            decoded = self._eval_id_decoding(webpage, ol_id)
            video_url = video_url % decoded
        except DecodeError as e:
            self.report_warning('%s; falling back to method with pairing' % e, video_id)
            title, video_url = self._pairing_method(video_id)

        title = title or self._og_search_title(webpage, default=None) or self._search_regex(
            r'''<span[^>]+class=(["'])title\1[^>]*>(?P<title>[^<]+)''', webpage,
            'title', default=None, group='title') or self._html_search_meta(
            'description', webpage, 'title', fatal=True)

        entries = self._parse_html5_media_entries(url, webpage, video_id)
        entry = entries[0] if entries else {}
        subtitles = entry.get('subtitles')

        info_dict = {
            'id': video_id,
            'title': title,
            'thumbnail': entry.get('thumbnail') or self._og_search_thumbnail(webpage, default=None),
            'url': video_url,
            # Seems all videos have extensions in their titles
            'ext': determine_ext(title, 'mp4'),
            'subtitles': subtitles,
        }
        return info_dict
