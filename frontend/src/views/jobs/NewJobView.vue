<template>
  <div class="new-job">
    <el-page-header @back="$router.back()" title="新建语义对齐任务" />
    
    <el-card class="job-form-card">
      <el-steps :active="activeStep" finish-status="success" align-center>
        <el-step title="选择 DDL 源" />
        <el-step title="选择目标本体" />
        <el-step title="配置参数" />
        <el-step title="确认" />
      </el-steps>

      <div class="step-content">
        <!-- Step 1 -->
        <div v-if="activeStep === 0" class="step-panel">
          <h3>选择 DDL 数据源</h3>
          <el-alert
            v-if="!selectedDDL"
            title="请从下方列表选择一个 DDL 文件版本"
            type="info"
            :closable="false"
          />
          <el-table
            :data="ddlFiles"
            v-loading="loadingDDL"
            highlight-current-row
            @current-change="handleDDLSelect"
            style="width: 100%; margin-top: 20px"
          >
            <el-table-column type="index" width="50" />
            <el-table-column prop="sourceTag" label="版本标签" min-width="150" />
            <el-table-column prop="erpSource" label="ERP来源" width="100" />
            <el-table-column prop="tableCount" label="表数量" width="100" />
            <el-table-column prop="parseStatus" label="解析状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getParseStatusType(row.parseStatus)" size="small">
                  {{ getParseStatusText(row.parseStatus) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- Step 2 -->
        <div v-if="activeStep === 1" class="step-panel">
          <h3>选择目标本体</h3>
          <el-alert
            v-if="!selectedTTL"
            title="请从下方列表选择一个 TTL 本体版本"
            type="info"
            :closable="false"
          />
          <el-table
            :data="ttlFiles"
            v-loading="loadingTTL"
            highlight-current-row
            @current-change="handleTTLSelect"
            style="width: 100%; margin-top: 20px"
          >
            <el-table-column type="index" width="50" />
            <el-table-column prop="ontologyTag" label="版本标签" min-width="150" />
            <el-table-column prop="ontologyType" label="本体类型" width="100" />
            <el-table-column prop="classCount" label="类数量" width="100" />
            <el-table-column prop="indexStatus" label="索引状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getIndexStatusType(row.indexStatus)" size="small">
                  {{ getIndexStatusText(row.indexStatus) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- Step 3 -->
        <div v-if="activeStep === 2" class="step-panel">
          <h3>配置任务参数</h3>
          <el-form :model="form" label-width="120px" style="max-width: 500px; margin-top: 20px">
            <el-form-item label="任务名称" required>
              <el-input v-model="form.name" placeholder="例如：BIPV5财务域到FIBO对齐" />
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

        <!-- Step 4 -->
        <div v-if="activeStep === 3" class="step-panel">
          <h3>确认任务信息</h3>
          <el-descriptions :column="1" border style="margin-top: 20px">
            <el-descriptions-item label="任务名称">{{ form.name }}</el-descriptions-item>
            <el-descriptions-item label="任务描述">{{ form.description || '-' }}</el-descriptions-item>
            <el-descriptions-item label="DDL 源">{{ selectedDDL?.sourceTag }}</el-descriptions-item>
            <el-descriptions-item label="目标本体">{{ selectedTTL?.ontologyTag }}</el-descriptions-item>
            <el-descriptions-item label="并发数">{{ form.concurrency }}</el-descriptions-item>
            <el-descriptions-item label="批次大小">{{ form.batchSize }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>

      <div class="step-actions">
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
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { filesApi, jobsApi } from '@/api'
import type { DDLFile, TTLFile, JobCreateForm } from '@/types'

const router = useRouter()
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

const loadDDLFiles = async () => {
  loadingDDL.value = true
  try {
    const res = await filesApi.getDDLFiles({ page: 1, pageSize: 100 })
    ddlFiles.value = res.items
  } finally {
    loadingDDL.value = false
  }
}

const loadTTLFiles = async () => {
  loadingTTL.value = true
  try {
    const res = await filesApi.getTTLFiles({ page: 1, pageSize: 100 })
    ttlFiles.value = res.items
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
  if (activeStep.value < 3) activeStep.value++
}

const prevStep = () => {
  if (activeStep.value > 0) activeStep.value--
}

const submit = async () => {
  submitting.value = true
  try {
    const job = await jobsApi.createJob(form)
    ElMessage.success('任务创建成功')
    router.push(`/dashboard/job/${job.id}`)
  } catch (error) {
    ElMessage.error('创建任务失败')
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadDDLFiles()
  loadTTLFiles()
})
</script>

<style scoped>
.new-job {
  padding-bottom: 40px;
}

.job-form-card {
  margin-top: 20px;
}

.step-content {
  margin: 40px 0;
  min-height: 300px;
}

.step-panel h3 {
  margin: 0 0 16px;
  font-size: 16px;
  color: #303133;
}

.slider-value {
  margin-left: 12px;
  color: #409EFF;
  font-weight: 500;
}

.step-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
}
</style>
