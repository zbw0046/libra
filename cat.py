# 基金名称匹配（v2.0）
import multiprocessing
import os
import re
import time
from multiprocessing import Manager, Pool

import xlrd
import xlwt


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


word_replace_dict = {
    "国海富兰克林": "国海",
    "富兰克林国海": "国海",
    "富兰克林": "国海",
    "中国银河": "银河",
    "银河证券": "银河",
    "中国国际金融": "中金公司",
    "上海浦发银行": "浦发银行",
    "浦东发展银行": "浦发银行",
    "上海浦东银行": "浦发银行",
    "东方红": "东方证券"
}


def regulate_string(s):
    s = s.strip().replace('（', '(').replace('）', ')')
    for k in word_replace_dict:
        s = s.replace(k, word_replace_dict[k])
    return s


match_regex_dict = {}
chinese_re = re.compile(r'[^\x00-\x2f,\x3a-\xff]')


def match_string(a, b):
    short, long = regulate_string(a), regulate_string(b)
    if len(short) > len(long):
        short, long = long, short
    if short in match_regex_dict:
        regex = match_regex_dict[short]
    else:
        short_ch = chinese_re.findall(short)
        pattern = r"\S*".join(short_ch)
        # print(pattern)
        regex = re.compile(pattern)
        match_regex_dict[short] = regex
    if regex.search(long):
        return True
    else:
        return False

        # long_idx = 0
        # for i in range(len(short)):
        #     while short[i] != long[long_idx]:
        #         long_idx += 1
        #         if long_idx >= len(long):
        #             return False
        #         continue
        # return True


# match_string('大成成长回报六个月持有期混合型证券投资基金', '惠弘定期开放纯债债券型')


def check_wd_data(first_row):
    wd_col_name = ["证券代码", "证券简称", "基金管理人", "基金托管人", "基金获批注册日期", "发行公告日", "发行日期",
                   "个人投资者认购终止日", "机构投资者设立认购终止日", "基金成立日", "发行总份额\n[单位] 亿份", "上市日期", "投资类型(一级分类)",
                   "投资类型(二级分类)", "基金全称"]
    for i, col_name in enumerate(first_row):
        if i >= len(wd_col_name):
            return
        if wd_col_name[i] != col_name:
            raise Exception("col {} not in the right column in wd.xlsx".format(col_name))


# 拉取万德数据
# ('管理人', '托管人', '基金全称', 发行公告日期', '认购起始日',' 认购截止日', '基金成立日', '发行总份额',
# 'Wind一级分类', 'Wind二级分类', '基金代码')
def load_wd_data(wd_file):
    wd_rows = []
    wd_dict = {}
    sheet = xlrd.open_workbook(wd_file).sheets()[0]

    check_wd_data(sheet.row_values(0))
    for i in range(sheet.nrows):
        row = sheet.row_values(i)
        if not isinstance(row[0], str) or len(row[0]) < 7 or not row[0][:6].isdigit():
            continue
        wd_row = ['' for _ in range(11)]
        wd_row[0] = row[2]
        wd_row[1] = row[3]
        wd_row[2] = row[14].strip().replace('（', '(').replace('）', ')')
        # 万德的时间已经是yyyy-mm-dd的格式，因此无需再处理
        wd_row[3] = row[5]
        wd_row[4] = row[6]
        wd_row[5] = row[7]
        if wd_row[5] > row[8]:
            wd_row[5] = row[8]
        wd_row[6] = row[9]
        wd_row[7] = row[10]
        wd_row[8:10] = row[12:14]
        wd_row[10] = row[0]
        for j in range(len(wd_row)):
            if isinstance(wd_row[j], str):
                wd_row[j] = wd_row[j].strip()
        wd_rows.append(wd_row)
        wd_dict[wd_row[2]] = wd_row
    return wd_rows, wd_dict


def find_wd_row(wd_rows, guanli, tuoguan, quancheng, is_change, apply_date):
    for wd_row in wd_rows:
        if not is_change and len(wd_row[3]) > 6 and apply_date > wd_row[3]:
            # 如果不是变更注册，则跳过申请日晚于发行日的情况（匹配正确的话，申请日不可能晚于发行日）
            continue
        if match_string(guanli, wd_row[0]) and match_string(tuoguan, wd_row[1]) and match_string(quancheng, wd_row[2]):
            return wd_row
    return None


# zjh_weekly_row: (管理人，托管人，申请事项，申请日，受理日，决定日，是否为变更注册，变更注册代码)
def find_zjh_weekly_row_by_zjh_full_row(zjh_weekly_rows, guanli, quancheng, shenqingri):
    # todo: 优化：按时间做索引，避免遍历
    for zjh_weekly_row in zjh_weekly_rows:
        # 申请日
        if zjh_weekly_row[3] != shenqingri:
            continue
        if match_string(guanli, zjh_weekly_row[0]) and match_string(quancheng, zjh_weekly_row[2]):
            print('find_zjh_weekly_row_by_zjh_full_row: %s match (%s, %s, %s)' % (zjh_weekly_row, guanli, quancheng,
                                                                                  shenqingri))
            return zjh_weekly_row
    return None


# wd_db = load_wd_data('wd.xlsx')
# row = find_wd_row(wd_db, '广发', '建设银行', '广发安泰稳健养老目标一年持有期发起式基金中基金（FOF）')
# print(row)


# load data into memory
def load_db(result_xls_path):
    easy_db = []
    normal_db = []
    if os.path.exists(result_xls_path):
        result_easy_sheet = xlrd.open_workbook(result_xls_path).sheets()[0]
        result_normal_sheet = xlrd.open_workbook(result_xls_path).sheets()[1]
        nrows_easy = result_easy_sheet.nrows
        nrows_normal = result_normal_sheet.nrows
        for i in range(nrows_easy):
            if i < 1:
                continue
            easy_db_row = result_easy_sheet.row_values(i)[:20]
            for j in range(len(easy_db_row)):
                if isinstance(easy_db_row[j], str):
                    easy_db_row[j] = easy_db_row[j].strip()
            easy_db.append(easy_db_row)
        for i in range(nrows_normal):
            if i < 1:
                continue
            normal_db_row = result_normal_sheet.row_values(i)[:20]
            for j in range(len(normal_db_row)):
                if isinstance(normal_db_row[j], str):
                    normal_db_row[j] = normal_db_row[j].strip()
            normal_db.append(normal_db_row)

    return easy_db, normal_db


easy_title = ['基金管理人', '基金托管人', '申请事项', '申请日', '受理日（排序项）', '决定日', '发行公告日期', '认购起始日', ' 认购截止日',
              '基金成立日', '发行总份额', 'Wind一级分类', 'Wind二级分类', '一级分类', '二级分类', '是否为发起式', '是否为定期开放', '是否为港股通/香港主题',
              '是否为变更注册', '若为变更注册，原申请事项名称/代码']


# 仅非变更程序
def store_db_v2(new_db, file):
    f = xlwt.Workbook()
    easy_sheet = f.add_sheet('非变更程序', cell_overwrite_ok=True)
    print('非变更程序：%d' % len(new_db))
    temp_rows = [easy_title] + new_db
    for i, row in enumerate(temp_rows):
        print('add %d' % i)
        for j, item in enumerate(row):
            easy_sheet.write(i, j, item)
    f.save(file)


def store_db(easy_db, normal_db, file):
    f = xlwt.Workbook()
    easy_sheet = f.add_sheet('简易程序', cell_overwrite_ok=True)
    print('简易程序条目：%d' % len(easy_db))
    temp_rows = [easy_title] + easy_db
    for i, row in enumerate(temp_rows):
        print('add %d' % i)
        for j, item in enumerate(row):
            easy_sheet.write(i, j, item)
    normal_sheet = f.add_sheet('普通程序', cell_overwrite_ok=True)
    print('普通程序条目：$%d' % len(normal_db))
    temp_rows = [easy_title] + normal_db
    for i, row in enumerate(temp_rows):
        print('add %d' % i)
        for j, item in enumerate(row):
            normal_sheet.write(i, j, item)
    f.save(file)


def format_date_value(v):
    if not v:
        return v
    if isinstance(v, float):
        dt = xlrd.xldate_as_tuple(v, 0)
        return "%d-%02d-%02d" % (dt[0], dt[1], dt[2])
    if isinstance(v, str):
        dt = v.strip('）').strip(')').strip('受理').strip('（').strip('(')
        delim = "-"
        if "/" in v:
            delim = "/"
        dt = dt.split(delim)
        if len(dt) != 3:
            return v
        return "%d-%02d-%02d" % (int(dt[0]), int(dt[1]), int(dt[2]))
    raise Exception("unexpected type: {}".format(type(v)))


def format_easy_row(easy_row):
    for i in range(3, 10):
        easy_row[i] = format_date_value(easy_row[i])
    return easy_row


# 填充 一级分类
def classify_easy_row_c1(easy_row):
    full_name = easy_row[2].lower()
    wd_c2_class = easy_row[12]

    if "etf" in full_name:
        return "指数型"
    if "指数" in full_name:
        return "指数型"
    if "fof" in full_name:
        return "FOF"
    if "mom" in full_name:
        return "MOM"
    if "reits" in full_name:
        return "REITs"
    if "混合" in full_name:
        return "混合型"
    if "债券" in full_name:
        return "债券型"
    if "商品" in wd_c2_class:
        return "商品型"
    if "股票" in full_name:
        return "股票型"
    return "未知"


def classify_easy_row_c2(easy_row):
    full_name = easy_row[2].lower()
    c1_class = easy_row[13]
    if c1_class == "指数型":
        if "联接" in full_name:
            return "ETF联接"
        if "债" in full_name:
            return "债券指数型"
        if "交易型" in full_name:
            return "股票ETF"
        if "增强" in full_name:
            return "指数增强型"
        return "股票指数型"
    if c1_class == "债券型":
        for item in ("纯债", "可转债", "金融债", "利率债", "短债", "信用债"):
            if item in full_name:
                return "主题债券型"
        return "普通债券型"
    if c1_class == "FOF":
        if "目标日期" in full_name:
            return "目标日期FOF型"
        if "lof" in full_name:
            return "FOF-LOF型"
        return "目标风险FOF型"
    if c1_class == "MOM":
        if "混合" in full_name:
            return "混合型MOM"
        return ""
    if c1_class == "REITs":
        return "基础设施型"
    return ""


# 填充 '是否为发起式' ,'是否为定期开放', '是否为港股通/香港主题'
def autofill_easy_row(easy_row):
    full_name = easy_row[2].lower()
    if not easy_row[13]:
        easy_row[13] = classify_easy_row_c1(easy_row)
    if not easy_row[14]:
        easy_row[14] = classify_easy_row_c2(easy_row)
    easy_row[15] = '否'
    easy_row[16] = '否'
    easy_row[17] = '否'
    if '发起式' in full_name:
        easy_row[15] = '是'
    if '定开' in full_name or '定期开放' in full_name:
        easy_row[16] = '是'
    if '港' in full_name and '港口' not in full_name:
        easy_row[17] = '是'
    return easy_row


# 使用万德数据填充： wd_data: ('管理人', '托管人', '基金全称', 发行公告日期', '认购起始日',' 认购截止日', '基金成立日', '发行总份额',
# 'Wind一级分类', 'Wind二级分类')
def fulfill_row_with_wd_rows(easy_row, wd_rows):
    is_change = easy_row[19] == "是"
    wd_row = find_wd_row(wd_rows, easy_row[0], easy_row[1], easy_row[2], is_change, easy_row[3])
    if wd_row is None and is_change:
        # try use old name
        wd_row = find_wd_row(wd_rows, easy_row[0], easy_row[1], easy_row[19], is_change, easy_row[3])
    if wd_row is None:
        # no wd data
        return easy_row
    print('%s match %s' % (wd_row, easy_row))
    if not easy_row[6]:
        easy_row[6] = wd_row[3]
    if not easy_row[7]:
        easy_row[7] = wd_row[4]
    if not easy_row[8]:
        easy_row[8] = wd_row[5]
    if not easy_row[9]:
        easy_row[9] = wd_row[6]
    if not easy_row[10]:
        easy_row[10] = wd_row[7]
    if not easy_row[11]:
        easy_row[11] = wd_row[8]
    if not easy_row[12]:
        easy_row[12] = wd_row[9]
    return easy_row


# 使用万德数据填充： wd_data: ('管理人', '托管人', '基金全称', 发行公告日期', '认购起始日',' 认购截止日', '基金成立日', '发行总份额',
# 'Wind一级分类', 'Wind二级分类')
# return (found, fulfilled_row)
def fulfill_row_with_wd_dict(easy_row, wd_dict):
    quancheng = easy_row[2]
    if quancheng not in wd_dict:
        return False, None

    wd_row = wd_dict[quancheng]
    print('%s match %s' % (wd_row, easy_row))
    easy_row[1] = wd_row[1]
    if not easy_row[6]:
        easy_row[6] = wd_row[3]
    if not easy_row[7]:
        easy_row[7] = wd_row[4]
    if not easy_row[8]:
        easy_row[8] = wd_row[5]
    if not easy_row[9]:
        easy_row[9] = wd_row[6]
    if not easy_row[10]:
        easy_row[10] = wd_row[7]
    if not easy_row[11]:
        easy_row[11] = wd_row[8]
    if not easy_row[12]:
        easy_row[12] = wd_row[9]
    return True, easy_row


# zjh_weekly_row: (管理人，托管人，申请事项，申请日，受理日，决定日，是否为变更注册，变更注册代码)
def fulfill_row_with_zjh_weekly_rows(easy_row, zjh_weekly_rows):
    zjh_weekly_row = find_zjh_weekly_row_by_zjh_full_row(zjh_weekly_rows, easy_row[0], easy_row[2], easy_row[3])
    if not zjh_weekly_row:
        return easy_row
    if not easy_row[1]:
        easy_row[1] = zjh_weekly_row[1]
    easy_row[5] = zjh_weekly_row[5]

    easy_row[18] = zjh_weekly_row[6]
    easy_row[19] = zjh_weekly_row[7]
    return easy_row


# db_row: ['基金管理人', '基金托管人', '申请事项', '申请日', '受理日（排序项）', '决定日', '发行公告日期', '认购起始日', ' 认购截止日',
#               '基金成立日', '发行总份额', 'Wind一级分类', 'Wind二级分类', '一级分类', '二级分类', '是否为发起式', '是否为定期开放', '是否为港股通/香港主题',
#               '是否为变更注册', '若为变更注册，原申请事项名称/代码']
# zjh_full_row: # 0 接受材料日期（申请日）	1 公司名称（管理人）	2 基金名称	3受理日期	4补正日期	5一级分类	6二级分类	7备注
def complete_row_with_zjh_full_row(idx, db_row, wd_dict, zjh_full_row, zjh_weekly_rows):
    st = time.time()
    db_row[0] = zjh_full_row[1]
    db_row[2] = zjh_full_row[2]
    db_row[3] = zjh_full_row[0]
    db_row[4] = zjh_full_row[3]
    db_row[13:15] = zjh_full_row[5:7]
    # todo: 备注还没有加上

    found, fulfilled_db_row = fulfill_row_with_wd_dict(db_row, wd_dict)
    if not found:
        fulfilled_db_row = fulfill_row_with_zjh_weekly_rows(db_row, zjh_weekly_rows)

    db_row = autofill_easy_row(fulfilled_db_row)
    db_row = format_easy_row(db_row)
    et = time.time()
    print("process {} elapsed: {}".format(idx, et - st))
    return db_row


def complete_row_with_zjh_weekly_row(idx, db_row, wd_rows, zjh_row):
    t0 = time.time()
    db_row[0:6] = zjh_row[0:6]
    db_row[18:20] = zjh_row[6:8]

    db_row = fulfill_row_with_wd_rows(db_row, wd_rows)
    db_row = autofill_easy_row(db_row)
    db_row = format_easy_row(db_row)
    t1 = time.time()
    print("process {} elapsed: {}".format(idx, t1 - t0))
    return db_row


CPU_NUM = multiprocessing.cpu_count()
print("CPU NUM=%d" % CPU_NUM)


# 返回新的db
def fulfill_db_with_zjh_full(db, zjh_full_rows, wd_dict, zjh_weekly_rows):
    zjh_full_dict = {}
    db_dict = {}
    for row in db:
        db_dict[row[2]] = row
    for row in zjh_full_rows:
        zjh_full_dict[row[2]] = row

    n_tasks = len(db) + len(zjh_full_rows)
    n_fin = 0

    # update db: if not in zjh_full_dict, remove them; else update them use data from zjh_weekly and wd_data
    new_db = []
    pool = Pool(processes=CPU_NUM)
    with Manager() as ma:
        v_list = []
        for db_row in db:
            n_fin += 1
            print('%d/%d' % (n_fin, n_tasks))
            if db_row[2] not in zjh_full_dict:
                continue
            zjh_full_row = zjh_full_dict[db_row[2]]
            v = pool.apply_async(complete_row_with_zjh_full_row, args=(n_fin, db_row, wd_dict, zjh_full_row,
                                                                       zjh_weekly_rows))
            v_list.append(v)
        pool.close()
        pool.join()
        new_db += [v.get() for v in v_list]
    print("len of db: %d" % len(new_db))

    # for those in zjh_full_rows but not in db: fill fields using zjh_weekly and wd_data, then add them to the db
    pool = Pool(processes=CPU_NUM)
    with Manager() as ma:
        v_list = []
        for zjh_full_row in zjh_full_rows:
            n_fin += 1
            print('%d/%d' % (n_fin, n_tasks))
            if zjh_full_row[2] in db_dict:
                continue
            db_row = ['' for i in range(20)]
            v = pool.apply_async(complete_row_with_zjh_full_row, args=(n_fin, db_row, wd_dict, zjh_full_row,
                                                                       zjh_weekly_rows))
            v_list.append(v)
        pool.close()
        pool.join()
        new_db += [v.get() for v in v_list]
    print("len of db: %d" % len(new_db))

    new_db = sorted(new_db, key=lambda x: str(x[3]) + str(x[4]), reverse=True)

    return new_db


# 简易程序: zjh_row -> (管理人，托管人，申请事项，申请日，受理日，决定日，是否为变更注册，变更注册代码)
def extract_row_from_zjh_easy_add(zjh_xls_row, col_map):
    row = ['' for _ in range(8)]
    for i, val in enumerate(zjh_xls_row):
        correct_idx = col_map[i]
        if correct_idx == -1:
            continue
        row[correct_idx] = val
    row[2] = row[2].strip().replace('（', '(').replace('）', ')')
    row[3] = format_date_value(row[3])
    row[4] = format_date_value(row[4])
    row[5] = format_date_value(row[5])
    row[6] = '否'
    row[7] = ''
    return row


# 变更注册（简易）: zjh_row -> (管理人，托管人，申请事项，申请日，受理日，决定日，是否为变更注册，变更注册代码)
def extract_row_from_zjh_easy_change(zjh_xls_row, col_map):
    row = ['' for _ in range(8)]
    for i, val in enumerate(zjh_xls_row):
        correct_idx = col_map[i]
        if correct_idx == -1:
            continue
        row[correct_idx] = val
    row[2] = row[2].strip().replace('（', '(').replace('）', ')')
    row[3] = format_date_value(row[3])
    row[4] = format_date_value(row[4])
    row[5] = format_date_value(row[5])
    row[6] = '是'
    row[7] = row[7].strip().replace('（', '(').replace('）', ')')
    return row


# 普通程序：zjh_row -> (管理人，托管人，申请事项，申请日，受理日，决定日，是否为变更注册，变更注册代码)
def extract_row_from_zjh_normal_add(zjh_xls_row, col_map):
    row = ['' for _ in range(8)]
    for i, val in enumerate(zjh_xls_row):
        correct_idx = col_map[i]
        if correct_idx == -1:
            continue
        row[correct_idx] = val
    row[2] = row[2].strip().replace('（', '(').replace('）', ')')
    row[3] = format_date_value(row[3])
    row[4] = format_date_value(row[4])
    row[5] = format_date_value(row[5])
    row[6] = '否'
    row[7] = ''
    return row


# 变更注册（普通）：zjh_row -> (管理人，托管人，申请事项，申请日，受理日，决定日，是否为变更注册，变更注册代码)
def extract_row_from_zjh_normal_change(zjh_xls_row, col_map):
    row = ['' for _ in range(8)]
    for i, val in enumerate(zjh_xls_row):
        correct_idx = col_map[i]
        if correct_idx == -1:
            continue
        row[correct_idx] = val
    row[2] = row[2].strip().replace('（', '(').replace('）', ')')
    row[3] = format_date_value(row[3])
    row[4] = format_date_value(row[4])
    row[5] = format_date_value(row[5])
    row[6] = '是'
    row[7] = row[7].strip().replace('（', '(').replace('）', ')')
    return row


# (0 管理人，1 托管人，2申请事项，3 申请日，4 受理日，5 决定日，6 是否为变更注册，7 变更注册原事项)
def check_zjh_weekly_add_col_names(second_row, third_row):
    correct_col_name_list = ["基金管理人", "基金托管人", "申请事项", "申请材料接收日",
                             "受理决定或者不予受理决定日", "决定"]
    col_map = {}
    second_row = list(map(lambda x: x.strip(), second_row))
    third_row = list(map(lambda x: x.strip(), third_row))

    for i, col_name in enumerate(second_row):
        correct_idx = -1
        for j, correct_col_name in enumerate(correct_col_name_list):
            if col_name == correct_col_name:
                correct_idx = j
        col_map[i] = correct_idx
    for i, col_name in enumerate(third_row):
        correct_idx = -1
        for j, correct_col_name in enumerate(correct_col_name_list):
            if col_name == correct_col_name:
                correct_idx = j
        # 仅当有正确列时覆盖
        if correct_idx != -1:
            col_map[i] = correct_idx

    correct_col_exist = [False for i in range(len(correct_col_name_list))]
    for i in col_map.values():
        correct_col_exist[i] = True
    exist_tolerance = [False for _ in range(len(correct_col_name_list))]
    exist_tolerance[1] = True # 可以没有基金托管人
    for i, ex in enumerate(correct_col_exist):
        if not ex:
            if exist_tolerance[i]:
                print(bcolors.WARNING, "warn: {} not found in zjh_weekly (add)".format(correct_col_name_list[i]),
                      bcolors.ENDC)
            else:
                raise Exception("{} not found in zjh_weekly (add)".format(correct_col_name_list[i]))

    return col_map


# (0 管理人，1 托管人，2申请事项，3 申请日，4 受理日，5 决定日，6 是否为变更注册，7 变更注册原事项)
def check_zjh_weekly_change_col_names(second_row, third_row):
    correct_col_name_list = ["基金管理人", "基金托管人", "申请事项变更名称", "申请材料接收日",
                             "受理决定或者不予受理决定日", "决定", "是否变更注册", "申请事项原名称"]
    col_map = {}
    second_row = list(map(lambda x: x.strip(), second_row))
    third_row = list(map(lambda x: x.strip(), third_row))

    for i, col_name in enumerate(second_row):
        correct_idx = -1
        for j, correct_col_name in enumerate(correct_col_name_list):
            if col_name == correct_col_name:
                correct_idx = j
        col_map[i] = correct_idx
    for i, col_name in enumerate(third_row):
        correct_idx = -1
        for j, correct_col_name in enumerate(correct_col_name_list):
            if col_name == correct_col_name:
                correct_idx = j
        # 仅当有正确列时覆盖
        if correct_idx != -1:
            col_map[i] = correct_idx

    correct_col_exist = [False for i in range(len(correct_col_name_list))]
    for i in col_map.values():
        correct_col_exist[i] = True
    exist_tolerance = [False for _ in range(len(correct_col_name_list))]
    exist_tolerance[1] = True  # 可以没有基金托管人
    exist_tolerance[6] = True
    for i, ex in enumerate(correct_col_exist):
        if not ex:
            if exist_tolerance[i]:
                print(bcolors.WARNING, "warn: {} not found in zjh_weekly (change)".format(correct_col_name_list[i]),
                      bcolors.ENDC)
            else:
                raise Exception("{} not found in zjh_weekly (change)".format(correct_col_name_list[i]))

    return col_map


# zjh row -> data row
def extract_rows_from_zjh_weekly(zjh_filename):
    easy_rows = []
    easy_add_sheet = xlrd.open_workbook(zjh_filename).sheets()[0]
    easy_add_col_map = check_zjh_weekly_add_col_names(easy_add_sheet.row_values(1), easy_add_sheet.row_values(2))
    print("easy_add_col_map={}".format(easy_add_col_map))
    for i in range(easy_add_sheet.nrows):
        zjh_xls_row = easy_add_sheet.row_values(i)
        if not isinstance(zjh_xls_row[0], float):
            continue
        easy_row = extract_row_from_zjh_easy_add(zjh_xls_row, easy_add_col_map)
        print("easy_add_row={}".format(easy_row))
        for j in range(len(easy_row)):
            if isinstance(easy_row[j], str):
                easy_row[j] = easy_row[j].strip()
        easy_rows.append(easy_row)

    easy_change_sheet = xlrd.open_workbook(zjh_filename).sheets()[2]
    easy_change_col_map = check_zjh_weekly_change_col_names(easy_change_sheet.row_values(1),
                                                            easy_change_sheet.row_values(2))
    print("easy_change_col_map={}".format(easy_change_col_map))
    for i in range(easy_change_sheet.nrows):
        zjh_xls_row = easy_change_sheet.row_values(i)
        if not isinstance(zjh_xls_row[0], float):
            continue
        easy_row = extract_row_from_zjh_easy_change(zjh_xls_row, easy_change_col_map)
        print("easy_change_row={}".format(easy_row))
        for j in range(len(easy_row)):
            if isinstance(easy_row[j], str):
                easy_row[j] = easy_row[j].strip()
        easy_rows.append(easy_row)

    # normal
    normal_rows = []
    normal_add_sheet = xlrd.open_workbook(zjh_filename).sheets()[1]
    normal_add_col_map = check_zjh_weekly_add_col_names(normal_add_sheet.row_values(1), normal_add_sheet.row_values(2))
    print("normal_add_col_map={}".format(easy_add_col_map))
    for i in range(normal_add_sheet.nrows):
        zjh_xls_row = normal_add_sheet.row_values(i)
        if not isinstance(zjh_xls_row[0], float):
            continue
        row = extract_row_from_zjh_normal_add(zjh_xls_row, normal_add_col_map)
        print("normal_add_row={}".format(row))
        for j in range(len(row)):
            if isinstance(row[j], str):
                row[j] = row[j].strip()
        normal_rows.append(row)

    normal_change_sheet = xlrd.open_workbook(zjh_filename).sheets()[3]
    normal_change_col_map = check_zjh_weekly_change_col_names(normal_change_sheet.row_values(1),
                                                              normal_change_sheet.row_values(2))
    print("normal_change_col_map={}".format(normal_change_col_map))
    for i in range(normal_change_sheet.nrows):
        zjh_xls_row = normal_change_sheet.row_values(i)
        if not isinstance(zjh_xls_row[0], float):
            continue
        row = extract_row_from_zjh_normal_change(zjh_xls_row, normal_change_col_map)
        print("normal_change_row={}".format(row))
        for j in range(len(row)):
            if isinstance(row[j], str):
                row[j] = row[j].strip()
        normal_rows.append(row)

    return easy_rows, normal_rows


def check_zjh_full_col_name(first_row):
    correct_col_name_list = ["接受材料日期", "公司名称", "基金名称", "受理日期", "补正日期", "一级分类", "二级分类", "备注"]
    first_row = list(map(lambda x: x.strip(), first_row))
    exist_mark = [False for i in range(len(correct_col_name_list))]
    col_map = {}
    for i, col in enumerate(first_row):
        correct_row_idx = -1
        for j, name in enumerate(correct_col_name_list):
            if col == name:
                correct_row_idx = j
                exist_mark[j] = True
                break
        col_map[i] = correct_row_idx
    exist_tolerance = [False for _ in range(len(correct_col_name_list))]
    exist_tolerance[5] = True
    exist_tolerance[6] = True
    for i, ex in enumerate(exist_mark):
        if not ex:
            if exist_tolerance[i]:
                print(bcolors.WARNING, "warn: {} not found in zjh_full".format(correct_col_name_list[i]),
                      bcolors.ENDC)
            else:
                raise Exception("{} not found in zjh_full".format(correct_col_name_list[i]))
    return col_map


# 0 接受材料日期	1 公司名称（管理人）	2 基金名称	3受理日期	4补正日期	5一级分类	6二级分类	7备注
def extract_rows_from_zjh_full(zjh_full_filename):
    row_list = []
    zjh_full_sheet = xlrd.open_workbook(zjh_full_filename).sheets()[0]
    col_map = check_zjh_full_col_name(zjh_full_sheet.row_values(0))
    for i in range(1, zjh_full_sheet.nrows):
        zjh_xls_row = zjh_full_sheet.row_values(i)
        row = extract_row_from_zjh_full(zjh_xls_row, col_map)
        for j in range(len(row)):
            if isinstance(row[j], str):
                row[j] = row[j].strip()
        row_list.append(row)
    return row_list


# 0 接受材料日期	1 公司名称（管理人）	2 基金名称	3受理日期	4补正日期	5一级分类	6二级分类	7备注
def extract_row_from_zjh_full(zjh_full_row, col_map):
    row = ['' for _ in range(8)]
    for i, val in enumerate(zjh_full_row):
        correct_idx = col_map[i]
        if correct_idx == -1:
            continue
        row[correct_idx] = val

    row[2] = row[2].strip().replace('（', '(').replace('）', ')')
    row[3] = format_date_value(row[3])
    row[4] = format_date_value(row[4])
    return row


import shutil

if __name__ == "__main__":
    wd_path = "wd.xlsx"
    zjh_weekly_path = "zjh_weekly.xls"
    # update zjh xls
    # download_zjh_xls(zjh_weekly_path)

    t0 = time.time()
    result_xls = 'result_v2.xls'

    # todo: to remove after modify load_db:
    shutil.rmtree(result_xls, ignore_errors=True)

    easy_db, normal_db = load_db(result_xls)
    # wd_dict: quancheng -> row
    wd_rows, wd_dict = load_wd_data('wd.xlsx')

    zjh_full_rows = extract_rows_from_zjh_full("zjh_full.xlsx")
    zjh_weekly_easy_rows, zjh_weekly_normal_rows = extract_rows_from_zjh_weekly(zjh_weekly_path)
    zjh_weekly_rows = zjh_weekly_easy_rows + zjh_weekly_normal_rows

    new_db = fulfill_db_with_zjh_full(easy_db, zjh_full_rows, wd_dict, zjh_weekly_rows)

    store_db_v2(new_db, result_xls)

    # store_db(new_db, result_xls)
    t1 = time.time()
    print("all process elapsed: {}".format(t1 - t0))

    # match_string("华宝中证1000指数证券投资基金", "华宝中证金融科技主题交易型开放式指数证券投资基金发起式联接基金")
