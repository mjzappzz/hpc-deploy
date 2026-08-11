<template>
  <section class="page-section ops-commands-page">
    <el-card shadow="never" class="ops-overview-card">
      <div class="ops-overview">
        <div>
          <div class="ops-overview__title">常用运维命令</div>
          <div class="ops-overview__description">维护个人或团队常用命令。左侧选择标题，右侧默认只读查看；内容仅作记录和复制，不会下发到服务器执行。</div>
        </div>
        <el-button type="primary" @click="createDraft">新增命令</el-button>
      </div>
    </el-card>

    <el-alert title="请勿保存密码、私钥、Token 或其他凭据。高风险命令应在正文注明适用范围、验证与回退方式。" type="warning" :closable="false" class="ops-security-alert" />

    <div class="ops-workspace">
      <el-card shadow="never" class="ops-list-card">
        <template #header>
          <div class="ops-card-header">
            <span>命令列表</span>
            <el-tag size="small" effect="plain">{{ commands.length }}</el-tag>
          </div>
        </template>
        <el-input v-model="keyword" clearable placeholder="搜索标题" aria-label="搜索命令标题" />
        <el-scrollbar class="ops-command-list">
          <button
            v-for="command in filteredCommands"
            :key="command.id"
            type="button"
            class="ops-command-item"
            :class="{ 'is-active': selectedId === command.id }"
            @click="selectCommand(command)"
          >
            <span>{{ command.title }}</span>
            <small>{{ formatScriptUpdatedAt(command.updated_at) }}</small>
          </button>
          <el-empty v-if="!loading && filteredCommands.length === 0" :description="keyword ? '没有匹配的命令' : '还没有常用运维命令'" :image-size="72" />
        </el-scrollbar>
      </el-card>

      <el-card shadow="never" class="ops-editor-card" v-loading="loading">
        <template #header>
          <div class="ops-card-header">
            <span>{{ isEditing ? (selectedId === null ? '新增命令' : '编辑命令') : '命令详情' }}</span>
            <div class="ops-editor-actions">
              <el-button v-if="selectedId !== undefined" :disabled="!draft.content" @click="copyContent">复制内容</el-button>
              <el-button v-if="selectedId !== null && selectedId !== undefined && !isEditing" @click="startEditing">编辑</el-button>
              <el-button v-if="selectedId !== null && selectedId !== undefined && !isEditing" type="danger" plain @click="removeSelected">删除</el-button>
              <el-button v-if="isEditing" @click="cancelEditing">取消编辑</el-button>
              <el-button v-if="isEditing" type="primary" :loading="saving" :disabled="!draft.title.trim()" @click="saveCommand">保存</el-button>
            </div>
          </div>
        </template>

        <el-empty v-if="selectedId === undefined" description="从左侧选择一条命令，或新建命令。" />
        <el-form v-else-if="isEditing" label-position="top" class="ops-editor-form">
          <el-form-item label="标题" required>
            <el-input v-model="draft.title" maxlength="200" show-word-limit placeholder="例如：Ubuntu 开启 root SSH 登录" />
          </el-form-item>
          <el-form-item label="命令内容">
            <div class="ops-rich-editor">
              <div class="ops-rich-editor__toolbar" role="toolbar" aria-label="命令内容格式工具">
                <el-button size="small" @mousedown.prevent @click="toggleBold"><strong>B</strong>&nbsp; 加粗</el-button>
                <span>选中内容后点击加粗；粘贴内容将保持为纯文本。</span>
              </div>
              <div
                ref="editorRef"
                class="ops-rich-editor__content"
                contenteditable="true"
                role="textbox"
                aria-multiline="true"
                aria-label="命令内容"
                @input="syncEditorContent"
                @paste="handlePlainTextPaste"
              ></div>
            </div>
          </el-form-item>
        </el-form>
        <article v-else class="ops-command-detail">
          <h2>{{ draft.title }}</h2>
          <div v-if="draft.content" class="ops-command-rich-detail" v-html="draft.content"></div>
          <el-empty v-else description="（暂无命令内容）" :image-size="80" />
        </article>
      </el-card>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { requireAdminConfirm } from '@/composables/useAdminConfirm'
import { copyText } from '@/utils/clipboard'
import { getApiErrorMessage } from '@/utils/apiError'
import { opsCommandRichTextToPlainText } from '@/utils/richText'
import { formatScriptUpdatedAt } from '@/utils/time'
import {
  createOpsCommand,
  deleteOpsCommand,
  listOpsCommands,
  updateOpsCommand,
  type OpsCommand,
} from '@/api/opsCommand'

const commands = ref<OpsCommand[]>([])
const keyword = ref('')
const loading = ref(false)
const saving = ref(false)
const selectedId = ref<number | null | undefined>(undefined)
const isEditing = ref(false)
const draft = reactive({ title: '', content: '' })
const editorRef = ref<HTMLDivElement>()

const filteredCommands = computed(() => {
  const search = keyword.value.trim().toLowerCase()
  return search ? commands.value.filter((item) => item.title.toLowerCase().includes(search)) : commands.value
})

async function loadCommands() {
  loading.value = true
  try {
    commands.value = (await listOpsCommands()).data
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '加载常用运维命令失败'))
  } finally {
    loading.value = false
  }
}

function selectCommand(command: OpsCommand) {
  selectedId.value = command.id
  isEditing.value = false
  draft.title = command.title
  draft.content = command.content
}

function createDraft() {
  selectedId.value = null
  isEditing.value = true
  draft.title = ''
  draft.content = ''
  void nextTick(syncEditorFromDraft)
}

function syncEditorFromDraft() {
  if (editorRef.value) editorRef.value.innerHTML = draft.content
}

function syncEditorContent() {
  if (editorRef.value) draft.content = editorRef.value.innerHTML
}

function toggleBold() {
  editorRef.value?.focus()
  document.execCommand('bold')
  syncEditorContent()
}

function handlePlainTextPaste(event: ClipboardEvent) {
  event.preventDefault()
  document.execCommand('insertText', false, event.clipboardData?.getData('text/plain') ?? '')
  syncEditorContent()
}

async function saveCommand() {
  const title = draft.title.trim()
  if (!title) return
  const isCreate = selectedId.value === null
  const ok = await requireAdminConfirm(isCreate ? '新增常用运维命令' : '保存常用运维命令')
  if (!ok) return
  saving.value = true
  try {
    const payload = { title, content: draft.content }
    const saved = isCreate
      ? (await createOpsCommand(payload)).data
      : (await updateOpsCommand(selectedId.value!, payload)).data
    await loadCommands()
    selectCommand(saved)
    isEditing.value = false
    ElMessage.success(isCreate ? '常用运维命令已新增' : '常用运维命令已保存')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '保存常用运维命令失败'))
  } finally {
    saving.value = false
  }
}

function startEditing() {
  if (selectedId.value === null || selectedId.value === undefined) return
  isEditing.value = true
  void nextTick(syncEditorFromDraft)
}

function cancelEditing() {
  if (selectedId.value === null) {
    selectedId.value = undefined
    draft.title = ''
    draft.content = ''
  } else {
    const command = commands.value.find((item) => item.id === selectedId.value)
    if (command) {
      draft.title = command.title
      draft.content = command.content
    }
  }
  isEditing.value = false
}

async function removeSelected() {
  if (selectedId.value === null || selectedId.value === undefined) return
  const title = draft.title
  const ok = await requireAdminConfirm('删除常用运维命令')
  if (!ok) return
  await ElMessageBox.confirm(`确认删除“${title}”吗？`, '删除确认', { type: 'warning' })
  try {
    await deleteOpsCommand(selectedId.value)
    createDraft()
    await loadCommands()
    selectedId.value = undefined
    isEditing.value = false
    ElMessage.success('常用运维命令已删除')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '删除常用运维命令失败'))
  }
}

async function copyContent() {
  if (!draft.content) return
  try {
    const plainText = opsCommandRichTextToPlainText(draft.content)
    if (!await copyText(plainText)) throw new Error('clipboard unavailable')
    ElMessage.success('命令内容已复制')
  } catch {
    ElMessage.error('复制失败：浏览器未授予剪贴板权限')
  }
}

onMounted(loadCommands)
</script>

<style scoped>
.ops-overview-card,
.ops-list-card,
.ops-editor-card { border-radius: 20px; }
.ops-overview { display: flex; align-items: center; justify-content: space-between; gap: 24px; }
.ops-overview__title { font-size: 18px; font-weight: 600; }
.ops-overview__description { margin-top: 6px; color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.6; }
.ops-security-alert { margin-top: 16px; }
.ops-workspace { display: grid; grid-template-columns: minmax(260px, 0.36fr) minmax(0, 1fr); gap: 16px; margin-top: 16px; min-height: 620px; }
.ops-list-card, .ops-editor-card { min-width: 0; }
.ops-card-header, .ops-editor-actions { display: flex; align-items: center; }
.ops-card-header { justify-content: space-between; gap: 12px; }
.ops-editor-actions { gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.ops-command-list { height: 520px; margin-top: 12px; }
.ops-command-item { display: flex; width: 100%; flex-direction: column; gap: 6px; padding: 12px; border: 0; border-bottom: 1px solid var(--el-border-color-lighter); background: transparent; color: var(--el-text-color-primary); text-align: left; cursor: pointer; }
.ops-command-item:hover, .ops-command-item.is-active { background: var(--el-fill-color-light); }
.ops-command-item.is-active { box-shadow: inset 3px 0 0 var(--el-color-primary); }
.ops-command-item span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600; }
.ops-command-item small { color: var(--el-text-color-secondary); font-size: 12px; }
.ops-editor-form { max-width: none; }
.ops-command-detail h2 { margin: 0 0 16px; font-size: 18px; }
.ops-rich-editor { width: 100%; overflow: hidden; border: 1px solid var(--el-border-color); border-radius: 12px; background: var(--el-bg-color); }
.ops-rich-editor:focus-within { border-color: var(--el-color-primary); box-shadow: 0 0 0 1px var(--el-color-primary-light-7); }
.ops-rich-editor__toolbar { display: flex; align-items: center; gap: 12px; padding: 8px 10px; border-bottom: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-light); }
.ops-rich-editor__toolbar span { color: var(--el-text-color-secondary); font-size: 12px; }
.ops-rich-editor__content { min-height: 420px; max-height: 620px; padding: 16px; overflow: auto; outline: none; color: var(--el-text-color-primary); font: 13px/1.7 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; white-space: pre-wrap; word-break: break-word; }
.ops-command-rich-detail { min-height: 420px; padding: 16px; overflow: auto; border-radius: 12px; background: var(--el-fill-color-light); color: var(--el-text-color-primary); font: 13px/1.7 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; white-space: pre-wrap; word-break: break-word; }
.ops-command-rich-detail :deep(p), .ops-command-rich-detail :deep(div) { margin: 0 0 12px; }
.ops-command-rich-detail :deep(p:last-child), .ops-command-rich-detail :deep(div:last-child) { margin-bottom: 0; }
@media (max-width: 920px) { .ops-workspace { grid-template-columns: 1fr; } .ops-command-list { height: 260px; } }
@media (max-width: 640px) { .ops-overview, .ops-card-header { align-items: flex-start; flex-direction: column; } .ops-editor-actions { width: 100%; justify-content: flex-start; } }
</style>
