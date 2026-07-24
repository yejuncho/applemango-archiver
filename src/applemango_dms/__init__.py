__all__ = ["SequenceArchiverApp"]


def __getattr__(name):
	if name == "SequenceArchiverApp":
		from applemango_dms.app import SequenceArchiverApp

		return SequenceArchiverApp
	raise AttributeError(f"module 'applemango_dms' has no attribute {name!r}")