from docling.document_converter import DocumentConverter

converter = DocumentConverter()

def file_to_text(file) -> str:
    """ Convert file to markdown. """
    result = converter.convert(file)
    return result.document.export_to_markdown()
