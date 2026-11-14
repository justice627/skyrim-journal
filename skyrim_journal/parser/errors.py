class SaveParseError(Exception):
    """Base class; the message always says what failed and where."""


class BadMagicError(SaveParseError):
    pass


class TruncatedFileError(SaveParseError):
    pass


class UnsupportedVersionError(SaveParseError):
    pass


class DecompressionError(SaveParseError):
    pass


class FormatError(SaveParseError):
    """Data was readable but implausible (bad length, offset out of range...)."""


class ImplausibleLengthError(FormatError, TruncatedFileError):
    """A length field points past the end of data: truncation or corruption."""
