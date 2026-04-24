/**
 * 中国国家标准 GB/T 4754-2017《国民经济行业分类》
 * 门类（大类）列表，支持 el-select filterable 快速检索
 */
export interface IndustryOption {
  code: string
  label: string
  /** 拼音首字母，便于搜索 */
  pinyin: string
}

export const INDUSTRY_CATEGORIES: IndustryOption[] = [
  { code: 'A', label: '农、林、牧、渔业', pinyin: 'NLMMY' },
  { code: 'B', label: '采矿业', pinyin: 'CKY' },
  { code: 'C', label: '制造业', pinyin: 'ZZY' },
  { code: 'D', label: '电力、热力、燃气及水生产和供应业', pinyin: 'DLRLGRQSSCAGYY' },
  { code: 'E', label: '建筑业', pinyin: 'JZY' },
  { code: 'F', label: '批发和零售业', pinyin: 'PFHLSY' },
  { code: 'G', label: '交通运输、仓储和邮政业', pinyin: 'JTYSCHYZ' },
  { code: 'H', label: '住宿和餐饮业', pinyin: 'ZHCYY' },
  { code: 'I', label: '信息传输、软件和信息技术服务业', pinyin: 'XXCSRJHXXJSFWY' },
  { code: 'J', label: '金融业', pinyin: 'JRY' },
  { code: 'K', label: '房地产业', pinyin: 'FDCY' },
  { code: 'L', label: '租赁和商务服务业', pinyin: 'ZLHSWFY' },
  { code: 'M', label: '科学研究和技术服务业', pinyin: 'KXYJHJSFWY' },
  { code: 'N', label: '水利、环境和公共设施管理业', pinyin: 'SLHJGGJSSGLY' },
  { code: 'O', label: '居民服务、修理和其他服务业', pinyin: 'JMFWXLHQTFWY' },
  { code: 'P', label: '教育', pinyin: 'JY' },
  { code: 'Q', label: '卫生和社会工作', pinyin: 'WSHSHGZ' },
  { code: 'R', label: '文化、体育和娱乐业', pinyin: 'WHTYHYY' },
  { code: 'S', label: '公共管理、社会保障和社会组织', pinyin: 'GGGLSHBZHSHEHZZ' },
  { code: 'T', label: '国际组织', pinyin: 'GJZZ' },
]

/**
 * 自定义搜索过滤：支持按编码、中文名、拼音首字母搜索
 */
export function industryFilter(query: string, option: IndustryOption): boolean {
  if (!query) return true
  const q = query.toLowerCase()
  return (
    option.label.includes(q) ||
    option.code.toLowerCase().includes(q) ||
    option.pinyin.toLowerCase().includes(q)
  )
}
