<template>
  <section class="page" data-module="complaint">
    <header class="page-head">
      <div>
        <h2>投诉与回访管理</h2>
        <p class="page-desc">登记投诉来源、诉求描述与受理人，同一投诉只挂一条主记录；回访时限按最早一次受理起 48 小时，超期未回访的单子会高亮提示。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记投诉单</button>
        <button class="btn" type="button" @click="exportRows">导出投诉回访清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card" :class="{ 'stat-warn': item.warn }">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>关键字</span>
        <input v-model="keyword" placeholder="按投诉单号、来源、诉求、受理人检索" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetKeyword">重置条件</button>
    </form>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <template v-if="allRows.length">
      <section v-for="group in groups" :key="group.key" class="complaint-group">
        <h3 class="group-title">
          {{ group.title }}
          <span class="group-count">{{ groupRows(group.key).length }}</span>
        </h3>
        <table class="data-table">
          <thead>
            <tr>
              <th v-for="column in columns" :key="column">{{ column }}</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="row in groupRows(group.key)" :key="String(row.id)">
              <tr :class="{ 'row-overdue': row.超期 }">
                <td v-for="column in columns" :key="column">
                  <span v-if="column === '状态'" class="status-tag" :class="statusTagClass(row)">{{ row[column] }}</span>
                  <span v-else>{{ displayCell(row, column) }}</span>
                </td>
                <td class="row-actions">
                  <button v-if="row.status !== '已撤销'" class="link" type="button" @click="openVisit(row)">
                    {{ row.status === '已回访' ? '追加回访' : '登记回访' }}
                  </button>
                  <button
                    v-if="row.status === '待回访'"
                    class="link danger"
                    type="button"
                    @click="openMerge(row)"
                  >标记重复</button>
                  <button v-if="row.status !== '已撤销'" class="link danger" type="button" @click="revokeRow(row)">撤销</button>
                  <button class="link" type="button" @click="toggleDetail(row.id)">
                    {{ expandedId === row.id ? '收起详情' : '详情/历史' }}
                  </button>
                </td>
              </tr>
              <tr v-if="expandedId === row.id">
                <td :colspan="columns.length + 1" class="detail-cell">
                  <div class="detail-grid">
                    <div>
                      <h4>受理记录（{{ row.受理记录.length }} 次，时限按最早一次起算）</h4>
                      <ul class="history-list">
                        <li v-for="(item, idx) in row.受理记录" :key="idx">
                          {{ item.时间 }} · {{ item.受理人 }} 受理（{{ item.来源 }}）
                        </li>
                      </ul>
                    </div>
                    <div>
                      <h4>回访历史（{{ row.回访记录.length }} 次，历史结论保留）</h4>
                      <ul v-if="row.回访记录.length" class="history-list">
                        <li v-for="(item, idx) in row.回访记录" :key="idx">
                          {{ item.时间 }} · {{ item.回访人 }}：{{ item.结果 }}
                        </li>
                      </ul>
                      <p v-else class="muted-text">暂无回访记录{{ row.status === '已撤销' ? '（投诉已撤销，回访记录已清理）' : '' }}</p>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
            <tr v-if="!groupRows(group.key).length">
              <td :colspan="columns.length + 1" class="empty-state">{{ group.empty }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>
    <div v-else class="empty-block">
      <p class="empty-state">暂无投诉数据，可先点击右上角「登记投诉单」录入来源、诉求与受理人。</p>
    </div>

    <footer class="page-foot">
      <span>共 {{ total }} 条投诉记录 · 待回访 {{ groupsCount.pending }} · 已回访 {{ groupsCount.visited }} · 已撤销 {{ groupsCount.closed }}</span>
      <span class="muted-text">数据每次操作后重新拉取，重新打开页面看到的仍是最新结果</span>
    </footer>

    <!-- 登记投诉单 -->
    <div v-if="showCreate" class="modal-mask" @click.self="closeCreate">
      <div class="modal">
        <h3>登记投诉单</h3>
        <label class="form-item"><span>来源 *</span><input v-model="createForm.来源" placeholder="如：电话投诉、12345热线、现场反映" /></label>
        <label class="form-item"><span>诉求描述 *</span><textarea v-model="createForm.诉求描述" rows="3" placeholder="请描述投诉内容；与已有单同来源同描述会自动并入主记录"></textarea></label>
        <label class="form-item"><span>受理人 *</span><input v-model="createForm.受理人" placeholder="受理登记人姓名" /></label>
        <label class="form-item"><span>受理时间</span><input v-model="createForm.受理时间" placeholder="留空取当前时间，格式 2026-09-29 10:00" /></label>
        <p v-if="formMessage" class="error-text">{{ formMessage }}</p>
        <div class="modal-actions">
          <button class="btn" type="button" @click="closeCreate">取消</button>
          <button class="btn primary" type="button" :disabled="submitting" @click="submitCreate">保存</button>
        </div>
      </div>
    </div>

    <!-- 登记/追加回访 -->
    <div v-if="visitTarget" class="modal-mask" @click.self="closeVisit">
      <div class="modal">
        <h3>登记回访 · {{ visitTarget.投诉单号 }}</h3>
        <p class="muted-text">
          最早受理 {{ visitTarget.首次受理时间 }}，回访时限 {{ visitTarget.回访时限 }}
          <span v-if="visitTarget.超期" class="overdue-text">（已超期）</span>
        </p>
        <label class="form-item"><span>回访结果 *</span><textarea v-model="visitForm.回访结果" rows="3" placeholder="请填写回访结论；再次回访会追加保留，不覆盖历史结论"></textarea></label>
        <label class="form-item"><span>回访人</span><input v-model="visitForm.回访人" placeholder="留空默认取受理人" /></label>
        <label class="form-item"><span>回访时间</span><input v-model="visitForm.回访时间" placeholder="留空取当前时间" /></label>
        <p v-if="formMessage" class="error-text">{{ formMessage }}</p>
        <div class="modal-actions">
          <button class="btn" type="button" @click="closeVisit">取消</button>
          <button class="btn primary" type="button" :disabled="submitting" @click="submitVisit">保存回访</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

const ENDPOINT = '/api/complaint'

type HistoryItem = { 时间: string; 受理人?: string; 来源?: string; 回访人?: string; 结果?: string }
type Row = {
  id: number
  status: string
  投诉单号: string
  来源: string
  诉求描述: string
  受理人: string
  首次受理时间: string
  最新受理时间: string
  回访时限: string
  最新回访结果: string
  最新回访时间: string
  分组: 'pending' | 'visited' | 'closed'
  超期: boolean
  pending: boolean
  受理记录: HistoryItem[]
  回访记录: HistoryItem[]
  [key: string]: unknown
}

const columns = ['投诉单号', '来源', '诉求描述', '受理人', '首次受理时间', '回访时限', '最新回访结果', '最新回访时间', '状态']
const groups = [
  { key: 'pending', title: '待回访', empty: '暂无待回访投诉，新登记的投诉会出现在这里' },
  { key: 'visited', title: '已回访', empty: '暂无已回访投诉，登记回访结果后会出现在这里' },
  { key: 'closed', title: '已撤销 / 重复录入', empty: '暂无已撤销或并入主记录的投诉' },
] as const

const allRows = ref<Row[]>([])
const total = ref(0)
const keyword = ref('')
const errorMessage = ref('')
const expandedId = ref<number | null>(null)
const submitting = ref(false)

const showCreate = ref(false)
const createForm = reactive({ 来源: '', 诉求描述: '', 受理人: '', 受理时间: '' })
const visitTarget = ref<Row | null>(null)
const visitForm = reactive({ 回访结果: '', 回访人: '', 回访时间: '' })
const formMessage = ref('')

const groupsCount = computed(() => {
  const count = { pending: 0, visited: 0, closed: 0 }
  for (const row of allRows.value) count[row.分组] += 1
  return count
})
const overdueCount = computed(() => allRows.value.filter((row) => row.超期).length)
const stats = computed(() => [
  { label: '待回访', value: groupsCount.value.pending, warn: false },
  { label: '超期未回访', value: overdueCount.value, warn: overdueCount.value > 0 },
  { label: '已回访', value: groupsCount.value.visited, warn: false },
  { label: '已撤销/重复', value: groupsCount.value.closed, warn: false },
])

function groupRows(key: string): Row[] {
  return allRows.value.filter((row) => row.分组 === key)
}

function displayCell(row: Row, column: string): string {
  const value = row[column]
  if (value === null || value === undefined || value === '') {
    return column === '最新回访结果' || column === '最新回访时间' ? '待回访' : '—'
  }
  return String(value)
}

function statusTagClass(row: Row): Record<string, boolean> {
  return {
    'tag-pending': row.status === '待回访',
    'tag-done': row.status === '已回访',
    'tag-revoked': row.status === '已撤销',
    'tag-overdue': row.超期,
  }
}

function resetKeyword() {
  keyword.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function toggleDetail(id: number) {
  expandedId.value = expandedId.value === id ? null : id
}

// ---------- 登记 ----------

function openCreate() {
  formMessage.value = ''
  Object.assign(createForm, { 来源: '', 诉求描述: '', 受理人: '', 受理时间: '' })
  showCreate.value = true
}
function closeCreate() {
  showCreate.value = false
}

async function submitCreate() {
  formMessage.value = ''
  submitting.value = true
  try {
    const values: Record<string, string> = {
      来源: createForm.来源.trim(),
      诉求描述: createForm.诉求描述.trim(),
      受理人: createForm.受理人.trim(),
    }
    if (createForm.受理时间.trim()) values.受理时间 = createForm.受理时间.trim()
    const payload = await postJson('', values)
    formMessage.value = payload.message
    if (payload.ok) {
      showCreate.value = false
      await reload()
      errorMessage.value = ''
    }
  } catch (error) {
    formMessage.value = error instanceof Error ? error.message : '投诉登记失败'
  } finally {
    submitting.value = false
  }
}

// ---------- 回访 ----------

function openVisit(row: Row) {
  visitTarget.value = row
  formMessage.value = ''
  Object.assign(visitForm, { 回访结果: '', 回访人: '', 回访时间: '' })
}
function closeVisit() {
  visitTarget.value = null
}

async function submitVisit() {
  if (!visitTarget.value) return
  formMessage.value = ''
  submitting.value = true
  try {
    const values: Record<string, string> = { 回访结果: visitForm.回访结果.trim() }
    if (visitForm.回访人.trim()) values.回访人 = visitForm.回访人.trim()
    if (visitForm.回访时间.trim()) values.回访时间 = visitForm.回访时间.trim()
    const payload = await postJson(`/${visitTarget.value.id}/visits`, values)
    if (payload.ok) {
      visitTarget.value = null
      await reload()
    } else {
      formMessage.value = payload.message
    }
  } catch (error) {
    formMessage.value = error instanceof Error ? error.message : '回访登记失败'
  } finally {
    submitting.value = false
  }
}

// ---------- 撤销 / 合并 ----------

async function revokeRow(row: Row) {
  if (!window.confirm(`确认撤销投诉单 ${row.投诉单号}？撤销后其名下回访记录会一并清理。`)) return
  await actionJson(`/${row.id}/revoke`, {}, '投诉撤销失败')
}

async function openMerge(row: Row) {
  const input = window.prompt(
    `将 ${row.投诉单号} 标记为重复录入，请输入要并入的主记录投诉单号（如 COMP-0001）：`,
  )
  const code = (input ?? '').trim()
  if (!code) return
  const master = allRows.value.find((item) => item.投诉单号 === code)
  if (!master) {
    errorMessage.value = `主记录 ${code} 不在当前列表中，请确认投诉单号，或清空筛选条件后重试`
    return
  }
  await actionJson(`/${row.id}/merge`, { master_id: master.id }, '重复合并失败')
}

async function postJson(path: string, values: Record<string, string>): Promise<{ ok: boolean; message: string }> {
  const response = await request(`${ENDPOINT}${path}`, {
    method: 'POST',
    body: JSON.stringify({ values }),
  })
  if (!response.ok) throw new Error(`接口返回 ${response.status}，操作未生效`)
  return response.json()
}

async function actionJson(path: string, values: Record<string, unknown>, fallback: string) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}${path}`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    if (!response.ok) throw new Error(`接口返回 ${response.status}，操作未生效`)
    const payload = await response.json()
    if (!payload.ok) {
      errorMessage.value = payload.message
      return
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : fallback
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value.trim()) query.set('keyword', keyword.value.trim())
  query.set('size', '200')
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) throw new Error('投诉列表读取失败')
    const payload = await response.json()
    allRows.value = payload.items ?? []
    total.value = payload.total ?? allRows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '投诉列表读取失败'
    allRows.value = []
    total.value = 0
  }
}

onMounted(reload)
</script>
