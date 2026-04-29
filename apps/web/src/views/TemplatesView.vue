<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  archiveTemplate,
  createTemplate,
  listTemplates,
  updateTemplate,
  type ExecutorName,
  type TaskTemplate,
} from '@/api'
import { readableError } from '@/lib/errors'

const router = useRouter()
const executorOptions: Array<{ label: string; value: ExecutorName }> = [
  { label: 'Debug Printer', value: 'debug_printer' },
  { label: 'Claude Code', value: 'claude_code' },
  { label: 'Codex', value: 'codex' },
  { label: 'Kimi Code', value: 'kimi_code' },
]
const installDefaultExecutor = '' as const

const templates = ref<TaskTemplate[]>([])
const editingTemplate = ref<TaskTemplate | null>(null)
const name = ref('')
const description = ref('')
const defaultTaskTitle = ref('')
const defaultTargetWorkingDirectory = ref('')
const instructions = ref('')
const defaultExecutor = ref<ExecutorName | typeof installDefaultExecutor>('debug_printer')
const isLoading = ref(true)
const isSaving = ref(false)
const errorMessage = ref<string | null>(null)

const canSave = computed(() => name.value.trim().length > 0 && instructions.value.trim().length > 0)

onMounted(loadTemplates)

async function loadTemplates() {
  isLoading.value = true
  errorMessage.value = null
  try {
    const response = await listTemplates({ limit: 100 })
    templates.value = response.data
  } catch (error) {
    errorMessage.value = readableError(error)
  } finally {
    isLoading.value = false
  }
}

function editTemplate(template: TaskTemplate) {
  editingTemplate.value = template
  name.value = template.name
  description.value = template.description ?? ''
  defaultTaskTitle.value = template.default_task_title ?? ''
  defaultTargetWorkingDirectory.value = template.default_target_working_directory ?? ''
  instructions.value = template.instruction_source
  defaultExecutor.value = template.default_executor ?? installDefaultExecutor
}

function resetForm() {
  editingTemplate.value = null
  name.value = ''
  description.value = ''
  defaultTaskTitle.value = ''
  defaultTargetWorkingDirectory.value = ''
  instructions.value = ''
  defaultExecutor.value = 'debug_printer'
}

async function saveTemplate() {
  if (!canSave.value) {
    errorMessage.value = 'Add a name and instructions.'
    return
  }
  isSaving.value = true
  errorMessage.value = null
  try {
    if (editingTemplate.value) {
      await updateTemplate(editingTemplate.value.template_id, {
        version: editingTemplate.value.version,
        name: name.value.trim(),
        description: description.value.trim() || null,
        instruction_source: instructions.value.trim(),
        default_task_title: defaultTaskTitle.value.trim() || null,
        default_target_working_directory: defaultTargetWorkingDirectory.value.trim() || null,
        default_executor: defaultExecutor.value || null,
      })
    } else {
      await createTemplate({
        name: name.value.trim(),
        description: description.value.trim() || null,
        instruction_source: instructions.value.trim(),
        default_task_title: defaultTaskTitle.value.trim() || null,
        default_target_working_directory: defaultTargetWorkingDirectory.value.trim() || null,
        default_executor: defaultExecutor.value || null,
      })
    }
    resetForm()
    await loadTemplates()
  } catch (error) {
    errorMessage.value = readableError(error)
  } finally {
    isSaving.value = false
  }
}

async function archiveSelected(template: TaskTemplate) {
  errorMessage.value = null
  try {
    await archiveTemplate(template.template_id, template.version)
    if (editingTemplate.value?.template_id === template.template_id) {
      resetForm()
    }
    await loadTemplates()
  } catch (error) {
    errorMessage.value = readableError(error)
  }
}

async function useTemplate(template: TaskTemplate) {
  await router.push({ name: 'compose', query: { templateId: template.template_id } })
}
</script>

<template>
  <div class="grid max-w-6xl gap-7">
    <div
      v-if="errorMessage"
      class="rounded-md border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/30 px-4 py-3 text-sm font-medium text-red-800 dark:text-red-300"
    >
      {{ errorMessage }}
    </div>

    <section>
      <div class="mb-6">
        <p class="mb-2 text-xs font-bold tracking-wide text-teal-700 dark:text-teal-400 uppercase">
          Templates
        </p>
        <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950 dark:text-slate-50">
          Task Templates
        </h2>
      </div>

      <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div
          class="overflow-hidden rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
        >
          <div v-if="isLoading" class="px-4 py-8 text-sm text-slate-500 dark:text-slate-400">
            Loading templates...
          </div>
          <div
            v-else-if="templates.length === 0"
            class="px-4 py-8 text-sm text-slate-500 dark:text-slate-400"
          >
            No active templates
          </div>
          <table v-else class="w-full border-collapse text-left text-sm">
            <thead
              class="bg-slate-50 dark:bg-slate-800/50 text-xs font-bold tracking-wide text-slate-500 dark:text-slate-400 uppercase"
            >
              <tr>
                <th class="px-4 py-3">Name</th>
                <th class="px-4 py-3">Default Title</th>
                <th class="px-4 py-3">Target</th>
                <th class="px-4 py-3">Executor</th>
                <th class="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="template in templates"
                :key="template.template_id"
                class="border-t border-slate-100 dark:border-slate-800"
              >
                <td class="px-4 py-3">
                  <div class="font-semibold text-slate-950 dark:text-slate-50">
                    {{ template.name }}
                  </div>
                  <div class="mt-1 line-clamp-1 text-xs text-slate-500 dark:text-slate-400">
                    {{ template.description || template.instruction_source }}
                  </div>
                </td>
                <td class="px-4 py-3 text-slate-700 dark:text-slate-300">
                  {{ template.default_task_title || template.name }}
                </td>
                <td class="px-4 py-3 text-slate-700 dark:text-slate-300">
                  {{ template.default_target_working_directory || 'choose when creating' }}
                </td>
                <td class="px-4 py-3 text-slate-700 dark:text-slate-300">
                  {{ template.default_executor || 'install default' }}
                </td>
                <td class="px-4 py-3">
                  <div class="flex justify-end gap-2">
                    <button
                      class="min-h-9 rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 text-sm font-semibold text-slate-700 dark:text-slate-300 transition hover:border-teal-700 dark:hover:border-teal-500 hover:text-teal-800"
                      type="button"
                      @click="useTemplate(template)"
                    >
                      Use
                    </button>
                    <button
                      class="min-h-9 rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 text-sm font-semibold text-slate-700 dark:text-slate-300 transition hover:border-teal-700 dark:hover:border-teal-500 hover:text-teal-800"
                      type="button"
                      @click="editTemplate(template)"
                    >
                      Edit
                    </button>
                    <button
                      class="min-h-9 rounded-md border border-red-200 dark:border-red-800 bg-white dark:bg-slate-900 px-3 text-sm font-semibold text-red-700 dark:text-red-300 transition hover:border-red-400 hover:bg-red-50"
                      type="button"
                      @click="archiveSelected(template)"
                    >
                      Archive
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <form class="grid content-start gap-4" @submit.prevent="saveTemplate">
          <h3 class="m-0 text-lg font-bold tracking-normal text-slate-950 dark:text-slate-50">
            {{ editingTemplate ? 'Edit Template' : 'New Template' }}
          </h3>
          <label class="grid gap-2 font-semibold text-slate-700 dark:text-slate-300">
            <span>Name</span>
            <input
              v-model="name"
              class="w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2.5 text-slate-950 dark:text-slate-50 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
              type="text"
              placeholder="Nightly Research"
            />
          </label>
          <label class="grid gap-2 font-semibold text-slate-700 dark:text-slate-300">
            <span>Default Task Title</span>
            <input
              v-model="defaultTaskTitle"
              class="w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2.5 text-slate-950 dark:text-slate-50 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
              type="text"
              placeholder="Nightly Research Run"
            />
          </label>
          <label class="grid gap-2 font-semibold text-slate-700 dark:text-slate-300">
            <span>Description</span>
            <input
              v-model="description"
              class="w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2.5 text-slate-950 dark:text-slate-50 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
              type="text"
              placeholder="Reusable research workflow"
            />
          </label>
          <label class="grid gap-2 font-semibold text-slate-700 dark:text-slate-300">
            <span>Optional Target Directory</span>
            <input
              v-model="defaultTargetWorkingDirectory"
              class="w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2.5 text-slate-950 dark:text-slate-50 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
              type="text"
              placeholder="/Users/you/project"
            />
          </label>
          <label class="grid gap-2 font-semibold text-slate-700 dark:text-slate-300">
            <span>Instructions</span>
            <textarea
              v-model="instructions"
              class="w-full resize-y rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2.5 text-slate-950 dark:text-slate-50 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
              rows="8"
              placeholder="Describe the reusable AI work..."
            />
          </label>
          <label class="grid gap-2 font-semibold text-slate-700 dark:text-slate-300">
            <span>Default Executor</span>
            <select
              v-model="defaultExecutor"
              class="w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2.5 text-slate-950 dark:text-slate-50 shadow-xs outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
            >
              <option :value="installDefaultExecutor">Install default</option>
              <option v-for="option in executorOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>
          <div class="flex gap-2">
            <button
              class="min-h-10 rounded-md border border-transparent bg-teal-700 px-5 font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-55"
              type="submit"
              :disabled="!canSave || isSaving"
            >
              {{ isSaving ? 'Saving...' : editingTemplate ? 'Save Changes' : 'Create Template' }}
            </button>
            <button
              v-if="editingTemplate"
              class="min-h-10 rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-4 font-semibold text-slate-700 dark:text-slate-300 transition hover:border-teal-700 dark:hover:border-teal-500 hover:text-teal-800"
              type="button"
              @click="resetForm"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </section>
  </div>
</template>
