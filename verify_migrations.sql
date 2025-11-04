-- =====================================================
-- VERIFICATION SCRIPT
-- Run this in DBeaver to confirm everything worked
-- =====================================================

-- =====================================================
-- 1. CHECK ALL TABLES EXIST
-- =====================================================
SELECT 
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public' 
  AND table_name IN ('workflows', 'actions', 'schemas', 'sessions')
ORDER BY table_name;

-- Expected results:
-- actions     | 31
-- schemas     | 8
-- sessions    | (existing count + 1 for state column)
-- workflows   | 8

-- =====================================================
-- 2. CHECK SESSIONS.STATE COLUMN
-- =====================================================
SELECT 
    column_name, 
    data_type, 
    column_default,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'sessions' 
  AND column_name = 'state';

-- Expected result:
-- state | jsonb | '{}'::jsonb | NO

-- =====================================================
-- 3. CHECK ACTIONS TABLE STRUCTURE
-- =====================================================
SELECT 
    column_name,
    data_type,
    column_default,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'actions'
ORDER BY ordinal_position;

-- Should show 31 columns including:
-- id, instance_id, canonical_name, display_name, description, action_type, category
-- requires_auth, min_trust_score, allowed_user_tiers, blocked_user_tiers
-- opposite_action, api_endpoint, http_method, timeout_ms, execution_type
-- is_undoable, undo_action, undo_window_seconds
-- is_repeatable, max_executions_per_session, max_executions_per_day, min_repeat_interval_seconds
-- workflow_id, sequence_number, is_optional_step, parallel_group
-- config, is_active, created_at, updated_at

-- =====================================================
-- 4. CHECK SCHEMAS TABLE STRUCTURE
-- =====================================================
SELECT 
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'schemas'
ORDER BY ordinal_position;

-- Should show 8 columns:
-- id, brand_id, schema_key, required_fields, api_endpoint, cache_ttl_seconds, created_at, updated_at

-- =====================================================
-- 5. CHECK WORKFLOWS TABLE STRUCTURE
-- =====================================================
SELECT 
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'workflows'
ORDER BY ordinal_position;

-- Should show 8 columns:
-- id, instance_id, canonical_name, display_name, description, is_active, created_at, updated_at

-- =====================================================
-- 6. CHECK FOREIGN KEY CONSTRAINTS
-- =====================================================
SELECT
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    rc.delete_rule
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
JOIN information_schema.referential_constraints AS rc
    ON tc.constraint_name = rc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_name IN ('actions', 'schemas', 'workflows')
ORDER BY tc.table_name, tc.constraint_name;

-- Expected foreign keys:
-- actions -> instances (CASCADE)
-- actions -> workflows (SET NULL)
-- schemas -> brands (CASCADE)
-- workflows -> instances (CASCADE)

-- =====================================================
-- 7. CHECK INDEXES
-- =====================================================
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('actions', 'schemas', 'workflows')
ORDER BY tablename, indexname;

-- Expected indexes:
-- actions: idx_actions_instance_id, idx_actions_canonical_name, idx_actions_active, idx_actions_workflow_id
-- schemas: idx_schemas_brand_id, idx_schemas_key
-- workflows: idx_workflows_instance_id, idx_workflows_active

-- =====================================================
-- 8. CHECK UNIQUE CONSTRAINTS
-- =====================================================
SELECT
    tc.table_name,
    tc.constraint_name,
    kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
WHERE tc.constraint_type = 'UNIQUE'
  AND tc.table_name IN ('actions', 'schemas', 'workflows')
ORDER BY tc.table_name, tc.constraint_name;

-- Expected unique constraints:
-- actions: UNIQUE(instance_id, canonical_name)
-- schemas: UNIQUE(brand_id, schema_key)
-- workflows: UNIQUE(instance_id, canonical_name)

-- =====================================================
-- 9. CHECK TRIGGERS
-- =====================================================
SELECT
    trigger_name,
    event_object_table,
    action_statement
FROM information_schema.triggers
WHERE event_object_table IN ('actions', 'schemas', 'workflows')
ORDER BY event_object_table, trigger_name;

-- Expected triggers:
-- update_actions_updated_at on actions
-- update_schemas_updated_at on schemas
-- update_workflows_updated_at on workflows

-- =====================================================
-- 10. TEST INSERT (OPTIONAL - WILL FAIL IF NO DATA)
-- =====================================================
-- Only run this if you have existing instance_id and brand_id

/*
-- Test workflow insert
INSERT INTO workflows (instance_id, canonical_name, display_name)
VALUES ('YOUR_INSTANCE_ID', 'test_workflow', 'Test Workflow')
RETURNING id, canonical_name;

-- Test action insert
INSERT INTO actions (
    instance_id, 
    canonical_name, 
    display_name, 
    action_type
)
VALUES (
    'YOUR_INSTANCE_ID',
    'test_action',
    'Test Action',
    'SYSTEM_API'
)
RETURNING id, canonical_name;

-- Test schema insert
INSERT INTO schemas (
    brand_id,
    schema_key,
    required_fields,
    api_endpoint
)
VALUES (
    'YOUR_BRAND_ID',
    'test_schema',
    ARRAY['field1', 'field2'],
    '/api/test'
)
RETURNING id, schema_key;

-- Cleanup test data
DELETE FROM actions WHERE canonical_name = 'test_action';
DELETE FROM schemas WHERE schema_key = 'test_schema';
DELETE FROM workflows WHERE canonical_name = 'test_workflow';
*/

-- =====================================================
-- SUMMARY CHECK
-- =====================================================
SELECT 
    'Tables Created' as check_type,
    COUNT(*) as count,
    CASE 
        WHEN COUNT(*) = 3 THEN '✅ PASS'
        ELSE '❌ FAIL'
    END as status
FROM information_schema.tables
WHERE table_schema = 'public' 
  AND table_name IN ('workflows', 'actions', 'schemas')

UNION ALL

SELECT 
    'State Column Added',
    COUNT(*),
    CASE 
        WHEN COUNT(*) = 1 THEN '✅ PASS'
        ELSE '❌ FAIL'
    END
FROM information_schema.columns
WHERE table_name = 'sessions' AND column_name = 'state'

UNION ALL

SELECT 
    'Foreign Keys',
    COUNT(*),
    CASE 
        WHEN COUNT(*) >= 4 THEN '✅ PASS'
        ELSE '❌ FAIL'
    END
FROM information_schema.table_constraints
WHERE constraint_type = 'FOREIGN KEY'
  AND table_name IN ('actions', 'schemas', 'workflows')

UNION ALL

SELECT 
    'Indexes',
    COUNT(*),
    CASE 
        WHEN COUNT(*) >= 7 THEN '✅ PASS'
        ELSE '❌ FAIL'
    END
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('actions', 'schemas', 'workflows')

UNION ALL

SELECT 
    'Triggers',
    COUNT(*),
    CASE 
        WHEN COUNT(*) >= 3 THEN '✅ PASS'
        ELSE '❌ FAIL'
    END
FROM information_schema.triggers
WHERE event_object_table IN ('actions', 'schemas', 'workflows');
