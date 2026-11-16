from sqlalchemy import inspect, text
from src.config.database import Base, engine
from src import models


def _column_type(column):
    return column.type.compile(dialect=engine.dialect)


def migrate():
    # 新建缺失的表（含完整约束与索引）
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    # 旧库补列：仅追加可空列或带默认值的列，避免重建既有业务表
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        present = {c['name'] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in present:
                continue
            ddl = f'ALTER TABLE {table.name} ADD COLUMN {column.name} {_column_type(column)}'
            if column.nullable is False and column.default is not None:
                ddl += f" DEFAULT {column.default.arg!r}"
            with engine.begin() as conn:
                conn.execute(text(ddl))
        # 旧库补索引（create_all 不会为已存在的表追加新索引）
        present_indexes = {i['name'] for i in inspector.get_indexes(table.name)}
        for index in table.indexes:
            if index.name in present_indexes:
                continue
            with engine.begin() as conn:
                conn.execute(text(sqlite_or_pg_index_ddl(index)))


def sqlite_or_pg_index_ddl(index):
    cols = ', '.join(c.name for c in index.columns)
    where = ''
    dialect = engine.dialect.name
    if index.unique and dialect in ('sqlite', 'postgresql'):
        where_clause = index.dialect_options[dialect].get('where')
        if where_clause is not None:
            where = f' WHERE {where_clause.text}'
    unique = 'UNIQUE ' if index.unique else ''
    return f'CREATE {unique}INDEX IF NOT EXISTS {index.name} ON {index.table.name} ({cols}){where}'


if __name__ == '__main__':
    migrate()
