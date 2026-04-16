<template>
  <el-dialog
    v-model="visible"
    title="新建语义对齐任务"
    width="700px"
    :close-on-click-modal="false"
  >
    <el-steps :active="activeStep" finish-status="success" simple>
      <el-step title="选择 DDL 源" />
      <el-step title="选择目标本体" />
      <el-step title="配置参数" />
      <el-step title="确认" />
    </el-steps>

    <div class="step-content">
      <!-- Step 1: Select DDL -->
      <div v-if="activeStep === 0" class="step-panel">
        <h3>选择 DDL 数据源</h3>
        <p class="step-desc">请选择要解析的 DDL 文件版本</p>
        <el-table
          :data="ddlFiles"
          v-loading="loadingDDL"
          highlight-current-row
          @current-change="handleDDLSelect"
          style="width: 100%"
        >
          <el-table-column type="index" width="50" />
          <el-table-column prop="sourceTag" label="版本标签" min-width="150" />
          <el-table-column prop="erpSource" label="ERP来源" width="100" />
          <el-table-column prop="tableCount" label="表数量" width="100">
            <template #default="{ row }">
              {{ row.tableCount || '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="parseStatus" label="解析状态" width="100">
            <template #default="{ row }">
              <el-tag :type="getParseStatusType(row.parseStatus)" size="small">
                {{ getParseStatusText(row.parseStatus) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="uploadTime" label="上传时间" width="150" />
        </el-table>
        <div class="selected-info" v-if="form.ddlFileId">
          <el-alert
            :title="`已选择: ${selectedDDL?.sourceTag}`"
            type="success"
            :closable="false"
          />
        </div>
      </div>

      <!-- Step 2: Select TTL -->
      <div v-if="activeStep === 1" class="step-panel">
        <h3>选择目标本体</h3>
        <p class="step-desc">请选择要对齐的 FIBO 本体版本</p>
        <el-table
          :data="ttlFiles"
          v-loading="loadingTTL"
          highlight-current-row
          @current-change="handleTTLSelect"
          style="width: 100%"
        >
          <el-table-column type="index" width="50" />
          <el-table-column prop="ontologyTag" label="版本标签" min-width="150" />
          <el-table-column prop="ontologyType" label="本体类型" width="100" />
          <el-table-column prop="classCount" label="类数量" width="100">
            <template #default="{ row }">
              {{ row.classCount || '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="indexStatus" label="索引状态" width="100">
            <template #default="{ row }">
              <el-tag :type="getIndexStatusType(row.indexStatus)" size="small">
                {{ getIndexStatusText(row.indexStatus) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="uploadTime" label="上传时间" width="150" />
        </el-table>
        <div class="selected-info" v-if="form.ttlFileId">
          <el-alert
            :title="`已选择: ${selectedTTL?.ontologyTag}`"
            type="success"
            :closable="false"
          />
        </div>
      </div>

      <!-- Step 3: Configure -->
      <div v-if="activeStep === 2" class="step-panel">
        <h3>配置任务参数</h3>
        <el-form :model="form" label-width="120px">
          <el-form-item label="任务名称" required>
            <el-input
              v-model="form.name"
              placeholder="例如：BIPV5财务域到FIBO对齐"
            />
          </el-form-item>
          <el-form-item label="任务描述">
            <el-input
              v-model="form.description"
              type="textarea"
              rows="3"
              placeholder="可选：填写任务描述"
            />
          </el-form-item>
          <el-form-item label="并发数">
            <el-slider v-model="form.concurrency" :min="1" :max="10" show-stops />
            <span class="slider-value">{{ form.concurrency }}</span>
          </el-form-item>
          <el-form-item label="批次大小">
            <el-slider v-model="form.batchSize" :min="1" :max="20" show-stops />
            <span class="slider-value">{{ form.batchSize }}</span>
          </el-form-item>
        </el-form>
      </div>

      <!-- Step 4: Confirm -->
      <div v-if="activeStep === 3" class="step-panel">
        <h3>确认任务信息</h3>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="任务名称">{{ form.name }}</el-descriptions-item>
          <el-descriptions-item label="任务描述">{{ form.description || '-' }}</el-descriptions-item>
          <el-descriptions-item label="DDL 源">{{ selectedDDL?.sourceTag }}</el-descriptions-item>
          <el-descriptions-item label="目标本体">{{ selectedTTL?.ontologyTag }}</el-descriptions-item>
          <el-descriptions-item label="并发数">{{ form.concurrency }}</el-descriptions-item>
          <el-descriptions-item label="批次大小">{{ form.batchSize }}</el-descriptions-item>
        </el-descriptions>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button v-if="activeStep > 0" @click="prevStep">上一步</el-button>
        <el-button
          v-if="activeStep < 3"
          type="primary"
          @click="nextStep"
          :disabled="!canProceed"
        >
          下一步
        </el-button>
        <el-button
          v-if="activeStep === 3"
          type="primary"
          :loading="submitting"
          @click="submit"
        >
          开始对齐
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { filesApi, jobsApi } from '@/api'
import type { DDLFile, TTLFile, JobCreateForm, Job } from '@/types'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  success: [job: Job]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

// State
const activeStep = ref(0)
const loadingDDL = ref(false)
const loadingTTL = ref(false)
const submitting = ref(false)
const ddlFiles = ref<DDLFile[]>([])
const ttlFiles = ref<TTLFile[]>([])
const selectedDDL = ref<DDLFile | null>(null)
const selectedTTL = ref<TTLFile | null>(null)

const form = reactive<JobCreateForm>({
  name: '',
  description: '',
  ddlFileId: null,
  ttlFileId: null,
  concurrency: 5,
  batchSize: 5,
})

// Computed
const canProceed = computed(() => {
  switch (activeStep.value) {
    case 0:
      return !!form.ddlFileId
    case 1:
      return !!form.ttlFileId
    case 2:
      return !!form.name.trim()
    default:
      return true
  }
})

// Methods
const loadDDLFiles = async () => {
  loadingDDL.value = true
  try {
    const res = await filesApi.getDDLFiles({ page: 1, pageSize: 100 })
    ddlFiles.value = res.items
  } catch (error) {
    ElMessage.error('加载 DDL 文件失败')
  } finally {
    loadingDDL.value = false
  }
}

const loadTTLFiles = async () => {
  loadingTTL.value = true
  try {
    const res = await filesApi.getTTLFiles({ page: 1, pageSize: 100 })
    ttlFiles.value = res.items
  } catch (error) {
    ElMessage.error('加载 TTL 文件失败')
  } finally {
    loadingTTL.value = false
  }
}

const handleDDLSelect = (row: DDLFile) => {
  selectedDDL.value = row
  form.ddlFileId = row.id
}

const handleTTLSelect = (row: TTLFile) => {
  selectedTTL.value = row
  form.ttlFileId = row.id
}

const getParseStatusType = (status: string) => {
  const map: Record<string, string> = {
    pending: 'info',
    parsing: 'warning',
    completed: 'success',
    failed: 'danger',
  }
  return map[status] || 'info'
}

const getParseStatusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '待解析',
    parsing: '解析中',
    completed: '已完成',
    failed: '失败',
  }
  return map[status] || status
}

const getIndexStatusType = (status: string) => {
  const map: Record<string, string> = {
    pending: 'info',
    indexing: 'warning',
    completed: 'success',
    failed: 'danger',
  }
  return map[status] || 'info'
}

const getIndexStatusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '待索引',
    indexing: '索引中',
    completed: '已完成',
    failed: '失败',
  }
  return map[status] || status
}

const nextStep = () => {
  if (activeStep.value < 3) {
    activeStep.value++
  }
}

const prevStep = () => {
  if (activeStep.value > 0) {
    activeStep.value--
  }
}

const submit = async () => {
  submitting.value = true
  try {
    const job = await jobsApi.createJob(form)
    ElMessage.success('任务创建成功')
    emit('success', job)
    resetForm()
  } catch (error) {
    ElMessage.error('创建任务失败')
  } finally {
    submitting.value = false
  }
}

const resetForm = () => {
  activeStep.value = 0
  form.name = ''
  form.description = ''
  form.ddlFileId = null
  form.ttlFileId = null
  form.concurrency = 5
  form.batchSize = 5
  selectedDDL.value = null
  selectedTTL.value = null
}

// Watch
watch(visible, (val) => {
  if (val) {
    loadDDLFiles()
    loadTTLFiles()
  }
})
</script>

<style scoped>
.step-content {
  margin-top: 30px;
  min-height: 300px;
}

.step-panel h3 {
  margin: 0 0 8px;
  font-size: 16px;
  color: #303133;
}

.step-desc {
  margin: 0 0 20px;
  color: #909399;
  font-size: 14px;
}

.selected-info {
  margin-top: 20px;
}

.slider-value {
  margin-left: 12px;
  color: #409EFF;
  font-weight: 500;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
