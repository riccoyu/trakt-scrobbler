import logging
import re
import guessit
from functools import lru_cache
from pathlib import Path
from utils import cleanup_encoding, config

logger = logging.getLogger('trakt_scrobbler')
config = config.get('fileinfo', {})
whitelist = config.get('whitelist')
regexes = config.get('include_regexes', {})


def whitelist_file(file_path):
    if not whitelist:
        return True
    file_path = cleanup_encoding(file_path)
    parents = tuple(file_path.absolute().resolve().parents)
    return any(Path(path).resolve() in parents for path in whitelist)


def custom_regex(file_path):
    logger.debug('Trying to match custom regex.')
    path_posix = str(file_path.as_posix())
    for item_type, patterns in regexes.items():
        for pattern in patterns:
            m = re.match(pattern, path_posix)
            if m:
                logger.debug(f"Matched pattern '{pattern}' for '{path_posix}'")
                guess = m.groupdict()
                guess['type'] = item_type
                return guess


def use_guessit(file_path):
    logger.debug('Using guessit module to match.')
    guess = guessit.guessit(str(file_path))
    logger.debug(guess)
    return guess


@lru_cache(maxsize=None)
def get_media_info(file_path):
    logger.debug(f"Filepath '{file_path}'")
    file_path = Path(file_path)
    if not whitelist_file(file_path):
        logger.info("File path not in whitelist.")
        return None
    guess = custom_regex(file_path) or use_guessit(file_path)

    if any(key not in guess for key in ('title', 'type')) or \
       (guess['type'] == 'episode' and 'episode' not in guess):
        logger.warning('Failed to parse filename for episode/movie info. '
                       'Consider renaming/using custom regex.')
        return None

    if isinstance(guess['title'], list):
        guess['title'] = " ".join(guess['title'])

    req_keys = ['type', 'title']
    if guess['type'] == 'episode':
        season = guess.get('season', 1)
        if isinstance(season, list):
            logger.warning(f"Multiple probable seasons found: ({','.join(season)}). "
                           "Consider renaming the folder.")
            return None
        guess['season'] = int(season)
        req_keys += ['season', 'episode']

    return {key: guess[key] for key in req_keys}
