<template>
  <div class="reviews">
    <div class="page-header">
      <h1>稽核管理</h1>
    </div>

    <el-card>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="待审核" name="pending">
          <el-table :data="pendingReviews" v-loading="loading" stripe>
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="databaseName" label="数据库" width="120" />
            <el-table-column prop="tableName" label="表名" width="150" />
            <el-table-column prop="fieldName" label="字段名" width="150" />
            <el-table-column prop="issueType" label="问题类型" width="120" />
            <el-table-column prop="severity" label="严重度" width="100">
              <template #default="{ row }">
                <el-tag :type="getSeverityType(row.severity)" size="small">
                  {{ row.severity }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="问题描述" min-width="200" />
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button type="success" link size="small" @click="approve(row)">
                  通过
                </el-button>
                <el-button type="danger" link size="small" @click="reject(row)">
                  驳回
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="已审核" name="completed">
          <el-empty description="暂无已审核记录" />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { Review } from '@/types'

const loading = ref(false)
const activeTab = ref('pending')
const pendingReviews = ref<Review[]>([])

const getSeverityType = (severity: string) => {
  const map: Record<string, string> = {
    high: 'danger',
    medium: 'warning',
    low: 'info',
  }
  return map[severity] || 'info'
}

const loadReviews = async () => {
  loading.value = true
  // TODO: Call API
  pendingReviews.value = [
    {
      id: 1,
      mappingId: 1,
      databaseName: 'ctmfa',
      tableName: 'aa_billcondition',
      fieldName: 'cconditionvalue',
      issueType: '映射不确定',
      severity: 'medium',
      description: '字段语义不明确，需要人工确认',
      status: 'pending',
      createdAt: '2026-04-15T10:00:00Z',
    },
  ]
  loading.value = false
}

const approve = async (row: Review) => {
  ElMessage.success('审核通过')
  loadReviews()
}

const reject = async (row: Review) => {
  ElMessage.info('已驳回')
  loadReviews()
}

onMounted(() => {
  loadReviews()
})
</script>

<style scoped>
.reviews {
  padding-bottom: 40px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  color: #303133;
}
</style>
