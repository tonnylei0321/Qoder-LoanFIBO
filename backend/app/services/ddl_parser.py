"""DDL Parser - Parse CREATE TABLE statements from DDL files."""

import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
import sqlglot
from sqlglot import exp
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert

from backend.app.services.pipeline_state import PipelineState
from backend.app.models.table_registry import TableRegistry
from backend.app.database import async_session_factory


# Regex patterns for fallback parsing
CREATE_TABLE_PATTERN = re.compile(
    r'CREATE\s+TABLE\s+(?:`?)(\w+)(?:`?)\s*\((.*?)\)\s*(?:ENGINE|COMMENT|DEFAULT|$)',
    re.IGNORECASE | re.DOTALL
)

# Pattern to detect per-table database annotation in multi-db DDL files
# Matches: -- 数据库: <dbname>  (on its own line, immediately before CREATE TABLE)
DB_ANNOTATION_PATTERN = re.compile(r'^--\s*数据库:\s*(\S+)\s*$', re.MULTILINE)

COMMENT_PATTERN = re.compile(r"COMMENT\s*['\"](.+?)['\"]", re.IGNORECASE)
COLUMN_COMMENT_PATTERN = re.compile(
    r'`?(\w+)`?\s+([\w\(\)]+)\s*(?:NOT\s+NULL|DEFAULT\s+[^,]+)?\s*COMMENT\s*["\']([^"\']+)["\']',
    re.IGNORECASE
)


async def parse_ddl_node(state: PipelineState) -> PipelineState:
    """Parse DDL files and populate table_registry.
    
    This node:
    1. Reads DDL files from configured directory
    2. Extracts CREATE TABLE statements
    3. Parses table name, columns, types, comments
    4. Inserts into table_registry table
    """
    job_id = state['job_id']
    logger.info(f"[parse_ddl_node] Starting DDL parsing for job_id={job_id}")
    
    ddl_dir = Path(os.getenv("DDL_DIR", "./data/ddl"))
    
    if not ddl_dir.exists():
        logger.error(f"DDL directory not found: {ddl_dir}")
        state['error'] = f"DDL directory not found: {ddl_dir}"
        return state
    
    total_tables = 0
    success_count = 0
    error_count = 0
    
    async with async_session_factory() as db:
        for ddl_file in ddl_dir.glob("*.sql"):
            logger.info(f"Processing DDL file: {ddl_file.name}")
            
            # Fallback database name from filename (used when no inline annotation)
            filename_db = ddl_file.stem
            
            try:
                with open(ddl_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Parse all CREATE TABLE statements.
                # split_ddl_by_database handles multi-db files (-- 数据库: xxx annotations)
                # and single-db files (falls back to filename as database name).
                tables = split_and_parse_ddl(content, filename_db)
                
                for table_info in tables:
                    total_tables += 1
                    
                    try:
                        # Check if table already exists
                        existing = await db.execute(
                            select(TableRegistry).where(
                                TableRegistry.database_name == table_info['database_name'],
                                TableRegistry.table_name == table_info['table_name']
                            )
                        )
                        existing_record = existing.scalar_one_or_none()
                        if existing_record:
                            # UPDATE: refresh table_comment and parsed_fields if they were missing
                            if not existing_record.table_comment and table_info.get('table_comment'):
                                existing_record.table_comment = table_info['table_comment']
                            if existing_record.parsed_fields:
                                # Re-check if field comments are missing - update if DDL has them
                                has_comments = any(f.get('comment') for f in existing_record.parsed_fields)
                                new_has_comments = any(f.get('comment') for f in table_info.get('parsed_fields', []))
                                if not has_comments and new_has_comments:
                                    existing_record.parsed_fields = table_info['parsed_fields']
                            await db.commit()
                            logger.debug(f"Table already exists (refreshed comments): {table_info['database_name']}.{table_info['table_name']}")
                            continue
                        
                        # Insert into database
                        table_registry = TableRegistry(
                            database_name=table_info['database_name'],
                            table_name=table_info['table_name'],
                            table_comment=table_info.get('table_comment'),  # Save table-level comment
                            raw_ddl=table_info['raw_ddl'],
                            parsed_fields=table_info['parsed_fields'],
                            mapping_status='pending'
                        )
                        db.add(table_registry)
                        await db.commit()
                        success_count += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to insert table {table_info['table_name']}: {str(e)}")
                        await db.rollback()
                        error_count += 1
                        
            except Exception as e:
                logger.error(f"Failed to parse DDL file {ddl_file.name}: {str(e)}")
                error_count += 1
    
    logger.info(f"[parse_ddl_node] DDL parsing completed: total={total_tables}, success={success_count}, errors={error_count}")
    
    # Update job statistics
    await update_job_stats(job_id, total_tables)
    
    return state


async def update_job_stats(job_id: int, total_tables: int):
    """Update job total_tables count."""
    from backend.app.models.mapping_job import MappingJob
    
    async with async_session_factory() as db:
        job = await db.get(MappingJob, job_id)
        if job:
            job.total_tables = total_tables
            await db.commit()


def split_and_parse_ddl(content: str, fallback_db: str) -> List[Dict[str, Any]]:
    """Parse DDL content, supporting both single-db and multi-db files.

    Multi-db files contain per-table annotations of the form::

        -- 表: <table_name>
        -- 数据库: <db_name>
        CREATE TABLE ...

    For each CREATE TABLE block the database name is resolved from the closest
    preceding ``-- 数据库:`` annotation.  If no annotation is found the
    ``fallback_db`` (usually the filename stem) is used instead.
    """
    # Fast-path: check whether the file contains any inline DB annotations.
    # If not, just delegate to the existing parse_ddl_content.
    if not DB_ANNOTATION_PATTERN.search(content):
        return parse_ddl_content(content, fallback_db)

    # Split on CREATE TABLE boundaries, preserving the preceding comment block
    # so we can extract the -- 数据库: annotation for each table.
    # Strategy: scan line-by-line, accumulate comment lines, flush on CREATE TABLE.
    tables: List[Dict[str, Any]] = []
    current_db = fallback_db
    pending_lines: List[str] = []

    # We'll collect each (db_name, block_text) tuple then parse them.
    blocks: List[tuple] = []   # (database_name, raw_block_text)

    lines = content.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Track the most-recently-seen -- 数据库: annotation
        m = re.match(r'^--\s*数据库:\s*(\S+)', stripped)
        if m:
            current_db = m.group(1)
            pending_lines.append(line)
            i += 1
            continue

        if re.match(r'CREATE\s+TABLE', stripped, re.IGNORECASE):
            # Collect the full CREATE TABLE block (until the closing parenthesis line)
            block_lines = list(pending_lines)
            block_lines.append(line)
            i += 1
            depth = line.count('(') - line.count(')')
            while i < len(lines) and depth > 0:
                block_lines.append(lines[i])
                depth += lines[i].count('(') - lines[i].count(')')
                i += 1
            # Grab any trailing ENGINE/COMMENT options on the same logical statement
            while i < len(lines):
                peek = lines[i].strip()
                if peek.startswith('--') or peek == '' or re.match(r'CREATE\s+TABLE', peek, re.IGNORECASE):
                    break
                block_lines.append(lines[i])
                i += 1

            block_text = ''.join(block_lines)
            blocks.append((current_db, block_text))
            pending_lines = []
            continue

        pending_lines.append(line)
        i += 1

    # Parse each block individually using the per-table database name
    for db_name, block_text in blocks:
        parsed = parse_ddl_content(block_text, db_name)
        tables.extend(parsed)

    logger.info(f"split_and_parse_ddl: extracted {len(tables)} tables across "
                f"{len({db for db, _ in blocks})} databases")
    return tables


def parse_ddl_content(content: str, database_name: str) -> List[Dict[str, Any]]:
    """Parse DDL content and extract all CREATE TABLE statements.
    
    Args:
        content: DDL file content
        database_name: Database name from filename
        
    Returns:
        List of table info dictionaries
    """
    tables = []
    
    # Try sqlglot first
    try:
        statements = sqlglot.parse(content, read='mysql')
        
        for statement in statements:
            if isinstance(statement, exp.Create) and statement.kind == "TABLE":
                table_info = parse_create_table_sqlglot(statement, database_name, content)
                if table_info:
                    tables.append(table_info)
                    
    except Exception as e:
        logger.warning(f"sqlglot parsing failed, falling back to regex: {str(e)}")
        # Fallback to regex parsing
        tables = parse_ddl_regex(content, database_name)
    
    return tables


def parse_create_table_sqlglot(statement: exp.Create, database_name: str, raw_content: str) -> Optional[Dict[str, Any]]:
    """Parse CREATE TABLE using sqlglot."""
    try:
        # Extract table name
        table = statement.find(exp.Table)
        if not table:
            return None
        
        table_name = table.name
        
        # Extract schema (columns)
        schema = statement.find(exp.Schema)
        if not schema:
            return None
        
        fields = []
        primary_keys = []
        
        for expr in schema.expressions:
            if isinstance(expr, exp.ColumnDef):
                field_info = parse_column_def(expr)
                fields.append(field_info)
                
                # Check if primary key
                if field_info.get('is_primary_key'):
                    primary_keys.append(field_info['field_name'])
                    
            elif isinstance(expr, exp.PrimaryKey):
                # Extract primary key columns
                # sqlglot may yield exp.Column or exp.Identifier depending on dialect
                for col in expr.expressions:
                    if isinstance(col, (exp.Column, exp.Identifier)):
                        primary_keys.append(col.name)
        
        # Update primary key flags
        for field in fields:
            if field['field_name'] in primary_keys:
                field['is_primary_key'] = True
        
        # Extract table comment
        table_comment = extract_table_comment(raw_content, table_name)
        
        # Extract raw DDL for this table
        raw_ddl = extract_table_ddl(raw_content, table_name)
        
        return {
            'database_name': database_name,
            'table_name': table_name,
            'raw_ddl': raw_ddl or str(statement),
            'parsed_fields': fields,
            'table_comment': table_comment,
        }
        
    except Exception as e:
        logger.error(f"Failed to parse CREATE TABLE with sqlglot: {str(e)}")
        return None


def parse_column_def(column_def: exp.ColumnDef) -> Dict[str, Any]:
    """Parse a column definition."""
    field_name = column_def.name
    
    # Get column type
    kind = column_def.args.get('kind')
    field_type = str(kind) if kind else 'UNKNOWN'
    
    # Check constraints
    is_nullable = True
    is_primary_key = False
    default_value = None
    comment = None
    
    for constraint in column_def.constraints:
        # sqlglot wraps constraint details in constraint.kind
        constraint_kind = constraint.kind if hasattr(constraint, 'kind') else constraint
        if isinstance(constraint_kind, exp.NotNullColumnConstraint):
            is_nullable = False
        elif isinstance(constraint_kind, exp.PrimaryKeyColumnConstraint):
            is_primary_key = True
        elif isinstance(constraint_kind, exp.DefaultColumnConstraint):
            default_value = str(constraint_kind.this) if constraint_kind.this else None
        elif isinstance(constraint_kind, exp.CommentColumnConstraint):
            # Extract the string value from the comment expression
            comment_expr = constraint_kind.this
            if comment_expr is not None:
                raw = str(comment_expr)
                # Strip surrounding quotes if present
                comment = raw.strip("'\"")
    
    return {
        'field_name': field_name,
        'field_type': field_type,
        'is_nullable': is_nullable,
        'is_primary_key': is_primary_key,
        'default_value': default_value,
        'comment': comment,
    }


def parse_ddl_regex(content: str, database_name: str) -> List[Dict[str, Any]]:
    """Fallback DDL parsing using regex."""
    tables = []
    
    # Find all CREATE TABLE statements
    for match in CREATE_TABLE_PATTERN.finditer(content):
        table_name = match.group(1)
        columns_part = match.group(2)
        
        fields = []
        
        # Parse columns with comments
        for col_match in COLUMN_COMMENT_PATTERN.finditer(columns_part):
            field_name = col_match.group(1)
            field_type = col_match.group(2)
            comment = col_match.group(3)
            
            fields.append({
                'field_name': field_name,
                'field_type': field_type,
                'is_nullable': 'NOT NULL' not in columns_part.upper(),
                'is_primary_key': False,
                'default_value': None,
                'comment': comment,
            })
        
        # Extract table comment
        table_comment = extract_table_comment(content, table_name)
        
        # Extract raw DDL
        raw_ddl = extract_table_ddl(content, table_name)
        
        tables.append({
            'database_name': database_name,
            'table_name': table_name,
            'raw_ddl': raw_ddl or f"CREATE TABLE `{table_name}` ({columns_part})",
            'parsed_fields': fields,
            'table_comment': table_comment,
        })
    
    return tables


def extract_table_comment(content: str, table_name: str) -> Optional[str]:
    """Extract table comment from DDL."""
    # Look for COMMENT='xxx' after table definition
    pattern = re.compile(
        rf'CREATE\s+TABLE\s+[`"]?(?:\w+\.)?{re.escape(table_name)}[`"]?.*?COMMENT\s*=\s*["\']([^"\']+)["\']',
        re.IGNORECASE | re.DOTALL
    )
    match = pattern.search(content)
    if match:
        return match.group(1)
    return None


def extract_table_ddl(content: str, table_name: str) -> Optional[str]:
    """Extract the complete CREATE TABLE statement."""
    # Find CREATE TABLE statement
    pattern = re.compile(
        rf'(CREATE\s+TABLE\s+[`"]?(?:\w+\.)?{re.escape(table_name)}[`"]?\s*\(.*?\)[^;]*;)',
        re.IGNORECASE | re.DOTALL
    )
    match = pattern.search(content)
    if match:
        return match.group(1).strip()
    return None


def parse_create_table(ddl_text: str) -> Optional[Dict[str, Any]]:
    """Parse a single CREATE TABLE statement (legacy function).
    
    Returns:
        Dict with database_name, table_name, parsed_fields
    """
    try:
        parsed = sqlglot.parse_one(ddl_text)
        
        if not isinstance(parsed, exp.Create):
            return None
        
        table = parsed.find(exp.Table)
        if not table:
            return None
        
        table_name = table.name
        
        fields = []
        schema = parsed.find(exp.Schema)
        if schema:
            for column_def in schema.expressions:
                if isinstance(column_def, exp.ColumnDef):
                    field_info = parse_column_def(column_def)
                    fields.append(field_info)
        
        return {
            'table_name': table_name,
            'parsed_fields': fields,
        }
    except Exception as e:
        logger.error(f"Failed to parse CREATE TABLE: {str(e)}")
        return None
