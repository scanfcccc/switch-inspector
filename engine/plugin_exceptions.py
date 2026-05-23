class PluginValidationError(Exception):
    """插件校验失败"""
    pass


class PluginLoadError(Exception):
    """插件加载失败"""
    pass


class PluginRuntimeError(Exception):
    """插件运行时错误（隔离用）"""
    pass
