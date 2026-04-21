<template>
  <div class="company-header">
    <!-- Company selector -->
    <div class="selector-row">
      <div class="selector-wrap">
        <el-icon class="selector-icon"><OfficeBuilding /></el-icon>
        <el-select
          v-model="selectedId"
          filterable
          remote
          :remote-method="searchCompanies"
          :loading="searching"
          placeholder="搜索或选择企业..."
          class="company-select"
          @change="handleSelect"
        >
          <el-option
            v-for="c in companyOptions"
            :key="c.id"
            :label="c.name"
            :value="c.id"
          >
            <div class="company-option">
              <span class="opt-name">{{ c.name }}</span>
              <span class="opt-meta">{{ c.industry }} · {{ c.region }}</span>
            </div>
          </el-option>
        </el-select>
      </div>

      <div class="date-wrap" v-if="company">
        <el-icon><Calendar /></el-icon>
        <span class="date-label">数据日期：{{ calcDate || '最新' }}</span>
      </div>
    </div>

    <!-- Company info card -->
    <transition name="fade-slide">
      <div v-if="company" class="company-info-card">
        <div class="info-main">
          <div class="company-avatar">
            {{ company.name.slice(0, 1) }}
          </div>
          <div class="info-details">
            <h2 class="company-name">{{ company.name }}</h2>
            <div class="info-meta">
              <span v-if="company.unified_code" class="meta-item">
                <el-icon><Ticket /></el-icon>
                {{ company.unified_code }}
              </span>
              <span v-if="company.industry" class="meta-item">
                <el-icon><OfficeBuilding /></el-icon>
                {{ company.industry }}
              </span>
              <span v-if="company.region" class="meta-item">
                <el-icon><Location /></el-icon>
                {{ company.region }}
              </span>
            </div>
          </div>
        </div>

        <!-- Regulatory tags (五篇大文章) -->
        <div class="reg-tags" v-if="activeTags.length > 0">
          <span class="tags-label">监管属性</span>
          <div class="tags-list">
            <span
              v-for="tag in activeTags"
              :key="tag.key"
              class="reg-tag"
              :class="tag.key"
            >
              <el-icon><Flag /></el-icon>
              {{ tag.label }}
            </span>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { loanAnalysisApi, type Company } from '@/api/loanAnalysis'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  modelValue?: string   // company id
  calcDate?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [id: string]
  'company-change': [company: Company]
}>()

const selectedId = ref(props.modelValue || '')
const company = ref<Company | null>(null)
const companyOptions = ref<Company[]>([])
const searching = ref(false)

// Regulatory tag labels
const tagLabels: Record<string, string> = {
  tech_finance: '科技金融',
  green_finance: '绿色金融',
  inclusive_finance: '普惠金融',
  pension_finance: '养老金融',
  digital_finance: '数字金融',
  implicit_debt: '隐性债务',
}

const activeTags = computed(() => {
  if (!company.value) return []
  return Object.entries(company.value.reg_tags)
    .filter(([, val]) => val)
    .map(([key]) => ({ key, label: tagLabels[key] || key }))
})

async function searchCompanies(query: string) {
  if (!query) return
  searching.value = true
  try {
    const result = await loanAnalysisApi.getCompanies({ search: query, page_size: 20 })
    companyOptions.value = result.items
  } catch {
    // ignore
  } finally {
    searching.value = false
  }
}

async function handleSelect(id: string) {
  if (!id) return
  try {
    company.value = await loanAnalysisApi.getCompany(id)
    emit('update:modelValue', id)
    emit('company-change', company.value)
  } catch {
    ElMessage.error('加载企业信息失败')
  }
}

// Load initial companies list
searchCompanies('')
loanAnalysisApi.getCompanies({ page_size: 20 }).then(r => {
  companyOptions.value = r.items
})

// Load company if id provided
watch(() => props.modelValue, async (id) => {
  if (id && id !== selectedId.value) {
    selectedId.value = id
    await handleSelect(id)
  }
}, { immediate: true })
</script>

<style scoped>
.company-header {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.selector-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.selector-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 300px;
}

.selector-icon {
  color: #667eea;
  font-size: 1.3rem;
  flex-shrink: 0;
}

.company-select {
  flex: 1;
}

:deep(.company-select .el-input__wrapper) {
  background: var(--input-bg);
  border: 1px solid var(--input-border);
  border-radius: 10px;
  box-shadow: none !important;
}

:deep(.company-select .el-input__inner) {
  color: var(--input-text-color);
}

.company-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 2px 0;
}

.opt-name {
  font-weight: 500;
  color: var(--text-primary);
  font-size: 0.9rem;
}

.opt-meta {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.date-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--date-label-color);
  font-size: 0.875rem;
  padding: 8px 14px;
  background: var(--input-bg);
  border: 1px solid var(--input-border);
  border-radius: 8px;
}

/* Company info card */
.company-info-card {
  background: var(--card-bg-subtle);
  border: 1px solid var(--card-border);
  border-radius: 16px;
  padding: 20px 24px;
  display: flex;
  align-items: flex-start;
  gap: 24px;
  flex-wrap: wrap;
}

.info-main {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  flex: 1;
}

.company-avatar {
  width: 52px;
  height: 52px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.4rem;
  font-weight: 700;
  color: white;
  flex-shrink: 0;
}

.company-name {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--company-name-color);
  margin: 0 0 8px;
}

.info-meta {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--meta-item-color);
  font-size: 0.85rem;
}

.meta-item .el-icon {
  font-size: 0.9rem;
  color: #667eea;
}

/* Regulatory tags */
.reg-tags {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.tags-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  white-space: nowrap;
}

.tags-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.reg-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 600;
  background: rgba(102, 126, 234, 0.12);
  color: #818cf8;
  border: 1px solid rgba(102, 126, 234, 0.3);
}

.reg-tag.green_finance {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
  border-color: rgba(16, 185, 129, 0.3);
}

.reg-tag.inclusive_finance {
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
  border-color: rgba(245, 158, 11, 0.3);
}

.reg-tag.implicit_debt {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  border-color: rgba(239, 68, 68, 0.3);
}

/* Transitions */
.fade-slide-enter-active { transition: all 0.3s ease; }
.fade-slide-leave-active { transition: all 0.2s ease; }
.fade-slide-enter-from { opacity: 0; transform: translateY(-8px); }
.fade-slide-leave-to   { opacity: 0; transform: translateY(-4px); }
</style>
