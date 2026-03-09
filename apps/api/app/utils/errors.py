class UnsupportedFileTypeError(ValueError):
    pass


class FileTooLargeError(ValueError):
    pass


class NeedsOCRError(ValueError):
    pass


class PasswordProtectedPDFError(ValueError):
    pass


class DocumentNotFoundError(ValueError):
    pass


class MetadataExtractionError(RuntimeError):
    pass


class EmbeddingGenerationError(RuntimeError):
    pass
