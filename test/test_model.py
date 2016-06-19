from glotpod.ident.model import metadata


def test_model_creatable(dbengine):
    metadata.create_all(dbengine)
    metadata.drop_all(dbengine)
