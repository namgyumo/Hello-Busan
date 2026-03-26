-- ============================================================
-- Hello-Busan  |  002_seed_categories.sql
-- 카테고리 초기 데이터 (6종)
-- ============================================================

INSERT INTO categories (id, name_ko, name_en, name_ja, name_zh, name_ru, icon, sort_order)
VALUES
    ('nature',    '자연/경관', 'Nature',      '自然/景観',  '自然/景观',  'Природа',       'mountain',   1),
    ('culture',   '문화/역사', 'Culture',     '文化/歴史',  '文化/历史',  'Культура',      'temple',     2),
    ('food',      '맛집/카페', 'Food & Cafe', 'グルメ/カフェ', '美食/咖啡', 'Еда и кафе',   'restaurant', 3),
    ('activity',  '액티비티',  'Activity',    'アクティビティ', '活动',     'Активности',    'sports',     4),
    ('shopping',  '쇼핑',      'Shopping',    'ショッピング',  '购物',     'Шопинг',        'bag',        5),
    ('nightview', '야경',      'Night View',  '夜景',       '夜景',      'Ночной вид',    'moon',       6)
ON CONFLICT (id) DO UPDATE SET
    name_ko    = EXCLUDED.name_ko,
    name_en    = EXCLUDED.name_en,
    name_ja    = EXCLUDED.name_ja,
    name_zh    = EXCLUDED.name_zh,
    name_ru    = EXCLUDED.name_ru,
    icon       = EXCLUDED.icon,
    sort_order = EXCLUDED.sort_order;
