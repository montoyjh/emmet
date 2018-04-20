from datetime import datetime

from maggma.builder import Builder
from tqdm import tqdm


class CopyBuilder(Builder):
    """Sync a source with a target.

    Uses `lu_field` of source and target Store to get new/updated documents.

    Can override `target.key` field to filter for target document to update.

    """

    def __init__(self, source, target, key=None, **kwargs):
        self.source = source
        self.target = target
        self.key = key if key else target.key
        super().__init__(sources=[source], targets=[target], **kwargs)

    def get_items(self):
        source, target = self.source, self.target
        lu_filter = source.lu_filter(target)
        self.logger.debug("lu_filter: {}".format(lu_filter))
        confirm_field_index(source, source.lu_field)
        if isinstance(self.key, str):
            target.ensure_index(self.key)
        confirm_field_index(target, self.key)
        cursor = source.query(criteria=lu_filter,
                              sort=[(source.lu_field, 1)])
        self.logger.info("Will copy {} items".format(cursor.count()))
        return iter(tqdm(cursor, total=cursor.count()))

    def process_item(self, item):
        return item

    def update_targets(self, items):
        source, target = self.source, self.target
        for item in items:
            # Use source last-updated value, ensuring `datetime` type.
            item[target.lu_field] = source.lu_func[0](item[source.lu_field])
            if source.lu_field != target.lu_field:
                del item[source.lu_field]
        target.update(items, update_lu=False, key=self.key)


def confirm_field_index(store, fields):
    """Confirm index on store for at least one of fields

    One can't simply ensure an index exists via
    `store.collection.create_index` because a Builder must assume
    read-only access to source Stores. The MongoDB `read` built-in role
    does not include the `createIndex` action.

    Raises:
        Exception: If there is no index on any of fields.

    """
    if not isinstance(fields, list):
        fields = [fields]
    info = store.collection.index_information().values()
    for spec in (index['key'] for index in info):
        for field in fields:
            if spec[0][0] == field:
                return
    raise Exception("Need index on one of '{}' for {}".format(
        fields, store.collection))
