<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  archiveTemplate,
  createTemplate,
  listExecutorProfiles,
  listTemplates,
  updateTemplate,
  type ExecutorProfile,
  type ExecutorName,
  type TaskTemplate,
} from '@/api'
import ErrorAlert from '@/components/ErrorAlert.vue'
import SelectField from '@/components/SelectField.vue'
import TextArea from '@/components/TextArea.vue'
import TextInput from '@/components/TextInput.vue'
import UiButton from '@/components/UiButton.vue'
import {
  defaultExecutorProfileId as defaultProfileId,
  executorProfileLabel,
  executorProfileOptions,
} from '@/lib/executors'
import { readableError } from '@/lib/errors'

const router = useRouter()
const installDefaultExecutor = '' as const

const templates = ref<TaskTemplate[]>([])
const executorProfiles = ref<ExecutorProfile[]>([])
const editingTemplate = ref<TaskTemplate | null>(null)
const name = ref('')
const description = ref('')
const defaultTaskTitle = ref('')
const defaultTargetWorkingDirectory = ref('')
const instructions = ref('')
const defaultExecutorProfileId = ref<string | typeof installDefaultExecutor>('')
const isLoading = ref(true)
const isSaving = ref(false)
const errorMessage = ref<string | null>(null)

const canSave = computed(() => name.value.trim().length > 0 && instructions.value.trim().length > 0)
const executorProfileSelectOptions = computed(() => executorProfileOptions(executorProfiles.value))

onMounted(loadTemplates)

async function loadTemplates() {
  isLoading.value = true
  errorMessage.value = null
  try {
    const [templatesResponse, profilesResponse] = await Promise.all([
      listTemplates({ limit: 100 }),
      listExecutorProfiles({ limit: 100 }),
    ])
    templates.value = templatesResponse.data
    executorProfiles.value = profilesResponse.data
    if (!defaultExecutorProfileId.value) {
      defaultExecutorProfileId.value = defaultExecutorProfileIdValue()
    }
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
  defaultExecutorProfileId.value = template.default_executor_profile_id ?? installDefaultExecutor
}

function resetForm() {
  editingTemplate.value = null
  name.value = ''
  description.value = ''
  defaultTaskTitle.value = ''
  defaultTargetWorkingDirectory.value = ''
  instructions.value = ''
  defaultExecutorProfileId.value = defaultExecutorProfileIdValue()
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
        default_executor: selectedExecutorForTemplate(),
        default_executor_profile_id: defaultExecutorProfileId.value || null,
      })
    } else {
      await createTemplate({
        name: name.value.trim(),
        description: description.value.trim() || null,
        instruction_source: instructions.value.trim(),
        default_task_title: defaultTaskTitle.value.trim() || null,
        default_target_working_directory: defaultTargetWorkingDirectory.value.trim() || null,
        default_executor: selectedExecutorForTemplate(),
        default_executor_profile_id: defaultExecutorProfileId.value || null,
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

function defaultExecutorProfileIdValue(): string {
  return defaultProfileId(executorProfiles.value)
}

function selectedExecutorForTemplate(): ExecutorName | null {
  if (!defaultExecutorProfileId.value) return null
  return (
    executorProfiles.value.find((profile) => profile.profile_id === defaultExecutorProfileId.value)
      ?.executor ?? null
  )
}

function templateExecutorLabel(template: TaskTemplate): string {
  const profile = executorProfiles.value.find(
    (candidate) => candidate.profile_id === template.default_executor_profile_id,
  )
  if (profile) return executorProfileLabel(profile)
  return template.default_executor || 'No default'
}
</script>

<template>
  <div class="grid max-w-6xl gap-7">
    <ErrorAlert :message="errorMessage" />

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
                  {{ templateExecutorLabel(template) }}
                </td>
                <td class="px-4 py-3">
                  <div class="flex justify-end gap-2">
                    <UiButton size="sm" @click="useTemplate(template)"> Use </UiButton>
                    <UiButton size="sm" @click="editTemplate(template)"> Edit </UiButton>
                    <UiButton size="sm" variant="danger" @click="archiveSelected(template)">
                      Archive
                    </UiButton>
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
          <TextInput v-model="name" label="Name" placeholder="Nightly Research" />
          <TextInput
            v-model="defaultTaskTitle"
            label="Default Task Title"
            placeholder="Nightly Research Run"
          />
          <TextInput
            v-model="description"
            label="Description"
            placeholder="Reusable research workflow"
          />
          <TextInput
            v-model="defaultTargetWorkingDirectory"
            label="Optional Target Directory"
            placeholder="/Users/you/project"
          />
          <TextArea
            v-model="instructions"
            label="Instructions"
            rows="8"
            placeholder="Describe the reusable AI work..."
          />
          <SelectField
            v-model="defaultExecutorProfileId"
            label="Default Executor Profile"
            :options="executorProfileSelectOptions"
            empty-label="Install default"
            :empty-value="installDefaultExecutor"
          />
          <div class="flex gap-2">
            <UiButton type="submit" variant="primary" :disabled="!canSave || isSaving">
              {{ isSaving ? 'Saving...' : editingTemplate ? 'Save Changes' : 'Create Template' }}
            </UiButton>
            <UiButton v-if="editingTemplate" @click="resetForm"> Cancel </UiButton>
          </div>
        </form>
      </div>
    </section>
  </div>
</template>
