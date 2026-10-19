def classFactory(iface):
    from .plugin import MetadataEditorPlugin
    return MetadataEditorPlugin(iface)
