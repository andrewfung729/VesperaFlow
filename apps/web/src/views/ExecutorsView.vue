<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  archiveExecutorProfile,
  createExecutorProfile,
  listExecutorProfiles,
  updateExecutorProfile,
  type ExecutorName,
  type ExecutorProfile,
} from '@/api'
import ErrorAlert from '@/components/ErrorAlert.vue'
import SelectField from '@/components/SelectField.vue'
import TextArea from '@/components/TextArea.vue'
import TextInput from '@/components/TextInput.vue'
import UiButton from '@/components/UiButton.vue'
import { readableError } from '@/lib/errors'
import { executorLabel, executorOptions, executorRegistry } from '@/lib/executors'

const profiles = ref<ExecutorProfile[]>([])
const editingProfile = ref<ExecutorProfile | null>(null)
const name = ref('')
const executor = ref<ExecutorName>('debug_printer')
const defaultModel = ref('')
const envText = ref('')
const secretEnvText = ref('')
const isEnabled = ref(true)
const isDefault = ref(false)
const isLoading = ref(true)
const isSaving = ref(false)
const errorMessage = ref<string | null>(null)

const canSave = computed(() => name.value.trim().length > 0)
const supportsModelSelection = computed(
  () => executorRegistry[executor.value].supportsModelSelection,
)

onMounted(loadProfiles)

async function loadProfiles() {
  isLoading.value = true
  errorMessage.value = null
  try {
    profiles.value = (await listExecutorProfiles({ limit: 100 })).data
  } catch (error) {
    errorMessage.value = readableError(error)
  } finally {
    isLoading.value = false
  }
}

function editProfile(profile: ExecutorProfile) {
  editingProfile.value = profile
  name.value = profile.name
  executor.value = profile.executor
  defaultModel.value = profile.default_model ?? ''
  envText.value = mapToLines(profile.env)
  secretEnvText.value = ''
  isEnabled.value = profile.is_enabled
  isDefault.value = profile.is_default
}

function resetForm() {
  editingProfile.value = null
  name.value = ''
  executor.value = 'debug_printer'
  defaultModel.value = ''
  envText.value = ''
  secretEnvText.value = ''
  isEnabled.value = true
  isDefault.value = false
}

async function saveProfile() {
  if (!canSave.value) {
    errorMessage.value = 'Add a profile name.'
    return
  }
  isSaving.value = true
  errorMessage.value = null
  try {
    const basePayload = {
      name: name.value.trim(),
      is_enabled: isEnabled.value,
      is_default: isDefault.value,
      env: parseEnvLines(envText.value),
    }
    const secretEnv = parseEnvLines(secretEnvText.value)
    if (editingProfile.value) {
      await updateExecutorProfile(editingProfile.value.profile_id, {
        version: editingProfile.value.version,
        ...basePayload,
        ...(supportsModelSelection.value
          ? { default_model: defaultModel.value.trim() || null }
          : {}),
        secret_env: secretEnv,
      })
    } else {
      await createExecutorProfile({
        executor: executor.value,
        ...basePayload,
        default_model: supportsModelSelection.value ? defaultModel.value.trim() || null : null,
        secret_env: secretEnv,
      })
    }
    resetForm()
    await loadProfiles()
  } catch (error) {
    errorMessage.value = readableError(error)
  } finally {
    isSaving.value = false
  }
}

async function archiveProfile(profile: ExecutorProfile) {
  errorMessage.value = null
  try {
    await archiveExecutorProfile(profile.profile_id, profile.version)
    if (editingProfile.value?.profile_id === profile.profile_id) resetForm()
    await loadProfiles()
  } catch (error) {
    errorMessage.value = readableError(error)
  }
}

function parseEnvLines(value: string): Record<string, string> {
  const result: Record<string, string> = {}
  for (const rawLine of value.split('\n')) {
    const line = rawLine.trim()
    if (!line) continue
    const separator = line.indexOf('=')
    if (separator <= 0) throw new Error(`Invalid env line: ${line}`)
    result[line.slice(0, separator).trim()] = line.slice(separator + 1)
  }
  return result
}

function mapToLines(value: Record<string, string>): string {
  return Object.entries(value)
    .map(([key, item]) => `${key}=${item}`)
    .join('\n')
}
</script>

<template>
  <div class="grid max-w-6xl gap-7">
    <ErrorAlert :message="errorMessage" />

    <section>
      <div class="mb-6">
        <p class="mb-2 text-xs font-bold tracking-wide text-teal-700 dark:text-teal-400 uppercase">
          Executors
        </p>
        <h2 class="m-0 text-2xl font-bold tracking-normal text-slate-950 dark:text-slate-50">
          Executor Profiles
        </h2>
      </div>

      <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div
          class="overflow-x-auto rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
        >
          <div v-if="isLoading" class="px-4 py-8 text-sm text-slate-500 dark:text-slate-400">
            Loading executor profiles...
          </div>
          <table v-else class="w-full border-collapse text-left text-sm">
            <thead
              class="bg-slate-50 dark:bg-slate-800/50 text-xs font-bold tracking-wide text-slate-500 dark:text-slate-400 uppercase"
            >
              <tr>
                <th class="px-4 py-3">Name</th>
                <th class="px-4 py-3">Executor</th>
                <th class="px-4 py-3">Model</th>
                <th class="px-4 py-3">Secrets</th>
                <th class="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="profile in profiles"
                :key="profile.profile_id"
                class="border-t border-slate-100 dark:border-slate-800"
              >
                <td class="px-4 py-3">
                  <div class="font-semibold text-slate-950 dark:text-slate-50">
                    {{ profile.name }}
                  </div>
                  <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    {{ profile.is_default ? 'default' : 'custom' }} ·
                    {{ profile.is_enabled ? 'enabled' : 'disabled' }}
                  </div>
                </td>
                <td class="px-4 py-3 text-slate-700 dark:text-slate-300">
                  {{ executorLabel(profile.executor) }}
                </td>
                <td class="px-4 py-3 text-slate-700 dark:text-slate-300">
                  {{ profile.default_model || 'executor default' }}
                </td>
                <td class="px-4 py-3 text-slate-700 dark:text-slate-300">
                  {{ profile.secret_env_keys.join(', ') || 'none' }}
                </td>
                <td class="px-4 py-3">
                  <div class="flex justify-end gap-2">
                    <UiButton size="sm" @click="editProfile(profile)"> Edit </UiButton>
                    <UiButton size="sm" variant="danger" @click="archiveProfile(profile)">
                      Archive
                    </UiButton>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <form class="grid content-start gap-4" @submit.prevent="saveProfile">
          <h3 class="m-0 text-lg font-bold tracking-normal text-slate-950 dark:text-slate-50">
            {{ editingProfile ? 'Edit Profile' : 'New Profile' }}
          </h3>
          <TextInput v-model="name" label="Name" placeholder="Codex GPT-5.2" />
          <SelectField
            v-model="executor"
            label="Executor"
            :options="executorOptions"
            :disabled="editingProfile !== null"
          />
          <TextInput
            v-if="supportsModelSelection"
            v-model="defaultModel"
            label="Default Model"
            placeholder="Executor default"
          />
          <label class="flex items-center gap-2 text-sm font-semibold text-slate-700">
            <input v-model="isEnabled" type="checkbox" />
            Enabled
          </label>
          <label class="flex items-center gap-2 text-sm font-semibold text-slate-700">
            <input v-model="isDefault" type="checkbox" />
            Default for executor
          </label>
          <TextArea v-model="envText" label="Env" rows="5" placeholder="FOO=bar" />
          <TextArea
            v-model="secretEnvText"
            label="Secret Env"
            rows="5"
            placeholder="ANTHROPIC_API_KEY=..."
          />
          <p
            v-if="editingProfile && editingProfile.secret_env_keys.length > 0"
            class="m-0 text-xs text-slate-500 dark:text-slate-400"
          >
            Existing secrets: {{ editingProfile.secret_env_keys.join(', ') }}
          </p>
          <div class="flex gap-2">
            <UiButton type="submit" variant="primary" :disabled="!canSave || isSaving">
              {{ isSaving ? 'Saving...' : editingProfile ? 'Save Changes' : 'Create Profile' }}
            </UiButton>
            <UiButton v-if="editingProfile" @click="resetForm"> Cancel </UiButton>
          </div>
        </form>
      </div>
    </section>
  </div>
</template>
