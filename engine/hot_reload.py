import logging
import os

from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer

logger = logging.getLogger("switch-inspector.hotreload")

_OBSERVER = None


class _RuleChangeHandler(PatternMatchingEventHandler):
    patterns = ["*.py"]
    ignore_directories = True

    def on_modified(self, event):
        if not event.is_directory:
            _reload_rules()

    def on_created(self, event):
        if not event.is_directory:
            _reload_rules()


def _get_alert_mgr():
    from engine.report import _get_alert_engine
    return _get_alert_engine()


def _reload_rules():
    try:
        mgr = _get_alert_mgr()
        if mgr is None:
            return
        old_names = set(mgr._rules.keys())
        mgr._rules.clear()
        mgr._enabled.clear()
        mgr.discover_rules()
        for name in list(mgr._rules.keys()):
            rule = mgr._rules[name]
            cfg = mgr._config.get(name, {})
            mgr.configure_rule(rule, cfg)
        new_names = set(mgr._rules.keys())
        diff = new_names - old_names
        if diff:
            logger.info("Hot-reload: new rules %s", sorted(diff))
        else:
            logger.info("Hot-reload: %d rules refreshed", len(new_names))
    except Exception as e:
        logger.error("Hot-reload failed: %s", e)


def auto_start(watch_path="rules"):
    global _OBSERVER
    if _OBSERVER is not None:
        return _OBSERVER
    if not os.path.isdir(watch_path):
        logger.warning("auto-reload: %s not found, disabled", watch_path)
        return None
    _OBSERVER = Observer()
    _OBSERVER.daemon = True
    _OBSERVER.schedule(_RuleChangeHandler(), watch_path, recursive=False)
    _OBSERVER.start()
    logger.info("Hot-reload watcher started on %s", watch_path)
    return _OBSERVER


def auto_stop():
    global _OBSERVER
    if _OBSERVER is None:
        return
    try:
        _OBSERVER.stop()
        _OBSERVER.join(timeout=3)
    except Exception:
        pass
    _OBSERVER = None
    logger.info("Hot-reload watcher stopped")
