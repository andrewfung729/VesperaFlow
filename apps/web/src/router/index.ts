import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import CalendarView from '@/views/CalendarView.vue'
import HistoryView from '@/views/HistoryView.vue'
import KanbanBoardView from '@/views/KanbanBoardView.vue'
import RecurringTodoView from '@/views/RecurringTodoView.vue'
import TaskComposerView from '@/views/TaskComposerView.vue'
import TaskDetailView from '@/views/TaskDetailView.vue'
import TemplatesView from '@/views/TemplatesView.vue'

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: { name: 'compose' },
  },
  {
    path: '/compose',
    name: 'compose',
    component: TaskComposerView,
  },
  {
    path: '/board',
    name: 'board',
    component: KanbanBoardView,
  },
  {
    path: '/templates',
    name: 'templates',
    component: TemplatesView,
  },
  {
    path: '/recurring',
    name: 'recurring-todo',
    component: RecurringTodoView,
  },
  {
    path: '/calendar',
    name: 'calendar',
    component: CalendarView,
  },
  {
    path: '/history',
    name: 'history',
    component: HistoryView,
  },
  {
    path: '/tasks/:taskId',
    name: 'task-detail',
    component: TaskDetailView,
    props: true,
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: { name: 'compose' },
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

export default router
