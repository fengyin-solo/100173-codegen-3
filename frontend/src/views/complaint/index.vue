<template>
  <section class="page" data-module="complaint">
    <header class="page-head">
      <div>
        <h2>投诉与回访管理</h2>
        <p class="page-desc">登记投诉单的来源、诉求与受理人，按待回访、已回访分组跟踪回访结果，超期未回访自动高亮。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记投诉单</button>
        <button class="btn" type="button" @click="exportRows">导出清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>关键词</span>
        <input v-model="filters.keyword" placeholder="投诉编号 / 来源 / 受理人 / 诉求" />
      </label>
      <label class="filter-item">
        <span>状态</span>
        <select v-model="filters.status">
          <option value="">全部</option>
          <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>超期</span>
        <select v-model="filters.overdue">
          <option value="">全部</option>
          <option value="true">仅看超期未回访</option>
          <option value="false">不含超期</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <div v-if="!rows.length && !errorMessage" class="empty-state-block">
      <p>暂无投诉与回访数据</p>
      <p class="empty-hint">可点击右上角「登记投诉单」录入第一条投诉，受理后即可在此跟踪回访进度。</p>
    </div>

    <template v-else>
      <!-- 待回访组 -->
      <div class="group-block">
        <h3 class="group-title">待回访 <span class="group-count">{{ pendingRows.length }}</span></h3>
        <table class="data-table">
          <thead>
            <tr>
              <th>投诉编号</th>
              <th>来源</th>
              <th>诉求描述</th>
              <th>受理人</th>
              <th>受理时间</th>
              <th>回访时限</th>
              <th>状态</th>
              <th>可执行动作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in pendingRows" :key="String(row.id)" :class="{ 'row-overdue': row.是否超期 }">
              <td>{{ row.投诉编号 }}</td>
              <td>{{ row.来源 }}</td>
              <td class="cell-desc">{{ row.诉求描述 }}</td>
              <td>{{ row.受理人 }}</td>
              <td>{{ row.受理时间 }}</td>
              <td>{{ row.回访时限 ?? '—' }}</td>
              <td>
                <span class="status-tag" :class="{ 'tag-overdue': row.是否超期 }">{{ row.status }}</span>
                <span v-if="row.是否超期" class="overdue-hint">超期未回访</span>
              </td>
              <td class="row-actions">
                <button class="link" type="button" @click="openVisit(row)">登记回访</button>
                <button class="link" type="button" @click="revoke(row)">撤销</button>
              </td>
            </tr>
            <tr v-if="!pendingRows.length">
              <td colspan="8" class="empty-state">暂无待回访投诉单</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 已回访组 -->
      <div class="group-block">
        <h3 class="group-title">已回访 <span class="group-count">{{ visitedRows.length }}</span></h3>
        <table class="data-table">
          <thead>
            <tr>
              <th>投诉编号</th>
              <th>来源</th>
              <th>诉求描述</th>
              <th>受理人</th>
              <th>受理时间</th>
              <th>回访结果</th>
              <th>回访方式</th>
              <th>回访人</th>
              <th>回访时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in visitedRows" :key="String(row.id)">
              <td>{{ row.投诉编号 }}</td>
              <td>{{ row.来源 }}</td>
              <td class="cell-desc">{{ row.诉求描述 }}</td>
              <td>{{ row.受理人 }}</td>
              <td>{{ row.受理时间 }}</td>
              <td><span class="result-tag" :class="`result-${row.回访结果}`">{{ row.回访结果 ?? '—' }}</span></td>
              <td>{{ row.回访方式 ?? '—' }}</td>
              <td>{{ row.回访人 ?? '—' }}</td>
              <td>{{ row.回访时间 ?? '—' }}</td>
            </tr>
            <tr v-if="!visitedRows.length">
              <td colspan="9" class="empty-state">暂无已回访投诉单</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 已撤销组 -->
      <div class="group-block">
        <h3 class="group-title">已撤销 <span class="group-count">{{ revokedRows.length }}</span></h3>
        <table class="data-table">
          <thead>
            <tr>
              <th>投诉编号</th>
              <th>来源</th>
              <th>诉求描述</th>
              <th>受理人</th>
              <th>受理时间</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in revokedRows" :key="String(row.id)">
              <td>{{ row.投诉编号 }}</td>
              <td>{{ row.来源 }}</td>
              <td class="cell-desc">{{ row.诉求描述 }}</td>
              <td>{{ row.受理人 }}</td>
              <td>{{ row.受理时间 }}</td>
              <td><span class="status-tag tag-revoked">{{ row.status }}</span></td>
            </tr>
            <tr v-if="!revokedRows.length">
              <td colspan="6" class="empty-state">暂无已撤销投诉单</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <footer class="page-foot">
      <span>共 {{ total }} 条投诉单 · 待回访 {{ pendingRows.length }} · 已回访 {{ visitedRows.length }} · 超期 {{ overdueCount }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 登记投诉单弹窗 -->
    <div v-if="showCreate" class="modal-mask" @click.self="showCreate = false">
      <div class="modal">
        <h3>登记投诉单</h3>
        <form @submit.prevent="submitCreate">
          <label class="form-item">
            <span>来源 <em>*</em></span>
            <select v-model="createForm.来源">
              <option value="">请选择来源</option>
              <option v-for="s in sources" :key="s" :value="s">{{ s }}</option>
            </select>
          </label>
          <label class="form-item">
            <span>诉求描述 <em>*</em></span>
            <textarea v-model="createForm.诉求描述" rows="3" placeholder="请描述投诉诉求" />
          </label>
          <label class="form-item">
            <span>受理人 <em>*</em></span>
            <input v-model="createForm.受理人" placeholder="受理人姓名" />
          </label>
          <label class="form-item">
            <span>受理时间</span>
            <input v-model="createForm.受理时间" placeholder="留空则取当前时间" />
          </label>
          <div class="modal-actions">
            <button class="btn primary" type="submit">提交登记</button>
            <button class="btn ghost" type="button" @click="showCreate = false">取消</button>
          </div>
        </form>
      </div>
    </div>

    <!-- 登记回访弹窗 -->
    <div v-if="showVisit" class="modal-mask" @click.self="showVisit = false">
      <div class="modal">
        <h3>登记回访 · {{ visitTarget?.投诉编号 }}</h3>
        <p class="modal-desc">{{ visitTarget?.来源 }} · {{ visitTarget?.诉求描述 }}</p>
        <form @submit.prevent="submitVisit">
          <label class="form-item">
            <span>回访结果 <em>*</em></span>
            <select v-model="visitForm.回访结果">
              <option value="">请选择回访结论</option>
              <option v-for="r in visitResults" :key="r" :value="r">{{ r }}</option>
            </select>
          </label>
          <label class="form-item">
            <span>回访方式</span>
            <select v-model="visitForm.回访方式">
              <option value="">请选择回访方式</option>
              <option v-for="m in visitMethods" :key="m" :value="m">{{ m }}</option>
            </select>
          </label>
          <label class="form-item">
            <span>回访人</span>
            <input v-model="visitForm.回访人" placeholder="回访人姓名" />
          </label>
          <div class="modal-actions">
            <button class="btn primary" type="submit">提交回访</button>
            <button class="btn ghost" type="button" @click="showVisit = false">取消</button>
          </div>
        </form>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null | boolean>

const ENDPOINT = '/api/complaint'
const statuses = ['待回访', '已回访', '已撤销']
const sources = ['来电', '来访', '来信', '网络', '上级转办']
const visitResults = ['满意', '基本满意', '不满意']
const visitMethods = ['电话', '上门', '信函']

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({ keyword: '', status: '', overdue: '' })

const showCreate = ref(false)
const createForm = ref<Record<string, string>>({ 来源: '', 诉求描述: '', 受理人: '', 受理时间: '' })

const showVisit = ref(false)
const visitTarget = ref<Row | null>(null)
const visitForm = ref<Record<string, string>>({ 回访结果: '', 回访方式: '', 回访人: '' })

const pendingRows = computed(() => rows.value.filter((row) => row.status === '待回访'))
const visitedRows = computed(() => rows.value.filter((row) => row.status === '已回访'))
const revokedRows = computed(() => rows.value.filter((row) => row.status === '已撤销'))
const overdueCount = computed(() => pendingRows.value.filter((row) => row.是否超期).length)

const stats = computed(() => [
  { label: '待回访', value: pendingRows.value.length },
  { label: '已回访', value: visitedRows.value.length },
  { label: '超期未回访', value: overdueCount.value },
])

function resetFilters() {
  filters.value = { keyword: '', status: '', overdue: '' }
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = { 来源: '', 诉求描述: '', 受理人: '', 受理时间: '' }
  showCreate.value = true
}

async function submitCreate() {
  errorMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm.value } }),
    })
    const payload = await response.json()
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.message || '投诉单登记失败')
    }
    showCreate.value = false
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '投诉单登记失败'
  }
}

function openVisit(row: Row) {
  visitTarget.value = row
  visitForm.value = { 回访结果: '', 回访方式: '', 回访人: '' }
  showVisit.value = true
}

async function submitVisit() {
  errorMessage.value = ''
  if (!visitTarget.value) return
  try {
    const response = await request(`${ENDPOINT}/${visitTarget.value.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: '登记回访', ...visitForm.value } }),
    })
    const payload = await response.json()
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.message || '回访登记失败')
    }
    showVisit.value = false
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '回访登记失败'
  }
}

async function revoke(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: '撤销' } }),
    })
    const payload = await response.json()
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.message || '撤销失败')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '撤销失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (filters.value.keyword) params.set('keyword', filters.value.keyword)
  if (filters.value.status) params.set('status', filters.value.status)
  if (filters.value.overdue) params.set('overdue', filters.value.overdue)
  const query = params.toString()
  try {
    const response = await request(`${ENDPOINT}${query ? `?${query}` : ''}`)
    if (!response.ok) {
      throw new Error('投诉与回访列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '投诉与回访列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.page-actions { display: flex; gap: 8px; }
.group-block { margin-bottom: 18px; }
.group-title { font-size: 15px; margin: 0 0 8px; color: #1f2937; }
.group-count { display: inline-block; min-width: 20px; padding: 0 6px; margin-left: 4px; background: #eef2ff; color: #1f6feb; border-radius: 10px; font-size: 12px; text-align: center; }
.cell-desc { max-width: 260px; }
.row-overdue { background: #fef3f2; }
.row-overdue td { color: #b42318; }
.status-tag { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 12px; background: #eef2ff; color: #1f6feb; }
.status-tag.tag-overdue { background: #fef3f2; color: #b42318; }
.status-tag.tag-revoked { background: #f1f5f9; color: #64748b; }
.overdue-hint { margin-left: 6px; font-size: 12px; color: #b42318; }
.result-tag { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 12px; }
.result-满意 { background: #ecfdf3; color: #027a48; }
.result-基本满意 { background: #fffaeb; color: #b54708; }
.result-不满意 { background: #fef3f2; color: #b42318; }
.empty-state-block { background: #fff; border: 1px dashed var(--border); border-radius: 8px; padding: 32px; text-align: center; color: var(--muted); }
.empty-hint { font-size: 13px; margin: 4px 0 0; }
.modal-mask { position: fixed; inset: 0; background: rgba(16, 24, 40, 0.45); display: flex; align-items: center; justify-content: center; z-index: 50; }
.modal { background: #fff; border-radius: 10px; padding: 20px; width: 420px; max-width: 92vw; }
.modal h3 { margin: 0 0 12px; font-size: 16px; }
.modal-desc { margin: 0 0 12px; font-size: 13px; color: var(--muted); }
.form-item { display: block; margin-bottom: 12px; }
.form-item span { display: block; font-size: 13px; color: #374151; margin-bottom: 4px; }
.form-item em { color: #b42318; font-style: normal; }
.form-item input, .form-item select, .form-item textarea { width: 100%; border: 1px solid var(--border); border-radius: 6px; padding: 6px 8px; font-size: 13px; font-family: inherit; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
</style>
