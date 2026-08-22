import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('places offline managed servers in a disabled section below online servers', async () => {
  const source = await readFile(new URL('./TaskRunner.vue', import.meta.url), 'utf8')

  assert.match(source, /v-for="group in managedServerGroups"/)
  assert.match(source, /v-for="server in group\.servers"/)
  assert.match(source, /group\.selectable/)
  assert.match(source, /离线服务器/)
  assert.match(source, /function toggleServerGroup\(groupServers: ServerRecord\[\]\)/)
  assert.match(source, /new Set\(selectedServerIds\.value\)/)
  assert.match(source, /const managedServerGroups = computed/)
  assert.match(source, /const TASK_SERVER_TAG_ORDER = \['待压测', '压测完成', '故障待处理', '测试机'\]/)
  assert.match(source, /'is-offline': server\.status === 'offline'/)
  assert.match(source, /:aria-disabled="server\.status !== 'online'"/)
  assert.match(source, /@click="server\.status === 'online' && toggleServerCard\(server\.id\)"/)
  assert.doesNotMatch(source, /我的关注/)
  assert.doesNotMatch(source, /groupedOnlineServers/)
})

test('labels the target-area probe action as detecting target servers', async () => {
  const source = await readFile(new URL('./TaskRunner.vue', import.meta.url), 'utf8')

  assert.match(source, /@click="probeTargetServers"/)
  assert.match(source, /检测目标服务器/)
  assert.match(source, /async function probeTargetServers\(\)/)
  assert.doesNotMatch(source, /检测在线服务器/)
})

test('lays task type modules side by side with vertically stacked cards', async () => {
  const source = await readFile(new URL('./TaskRunner.vue', import.meta.url), 'utf8')

  assert.match(source, /\.task-type-groups\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\)/)
  assert.match(source, /\.task-type-cards\s*\{[\s\S]*?grid-template-columns:\s*1fr/)
  assert.match(source, /@media \(max-width: 980px\)\s*\{[\s\S]*?\.task-type-groups\s*\{[\s\S]*?grid-template-columns:\s*1fr/)
  assert.match(source, /v-if="selectedTaskCategory === tt\.value" class="task-type-card-check"/)
  assert.match(source, /\.task-type-card-check\s*\{[\s\S]*?background: var\(--el-color-primary\)/)
})

test('uses danger styling when a target server has no CUDA Toolkit installed', async () => {
  const source = await readFile(new URL('./TaskRunner.vue', import.meta.url), 'utf8')

  assert.match(source, /'is-missing': cudaStatus\(server\) === '未安装'/)
  assert.match(source, /\.s-card-info-value\.is-missing\s*\{\s*color: var\(--el-color-danger\)/)
})

test('renders only safe disk targets and defaults to data mounts, not the system disk', async () => {
  const source = await readFile(new URL('./TaskRunner.vue', import.meta.url), 'utf8')

  assert.match(source, /v-for="group in diskTestServerGroups"/)
  assert.match(source, /v-model="diskTestDirsByServer\[group\.serverId\]"/)
  assert.match(source, /class="disk-mount-card-grid"/)
  assert.match(source, /'disk-mount-card'/)
  assert.match(source, /v-for="target in group\.targets"/)
  assert.match(source, /const diskTestDirsByServer = reactive<Record<number, string\[\]>>\(\{\}\)/)
  assert.match(source, /const diskTestServerGroups = computed\(\(\) =>/)
  assert.match(source, /mounted_filesystems/)
  assert.match(source, /disk_test_dirs_by_server/)
  assert.match(source, /Object\.assign\(diskTestDirsByServer, nextSelections\)/)
  assert.match(source, /filter\(isDiskStressMountpoint\)/)
  assert.match(source, /function isRecommendedDiskStressMountpoint\(mountpoint: string\)/)
  assert.match(source, /const preferredTarget = groupTargets\.find\(\(target\) => target\.mountpoint !== '\/'\) \?\? groupTargets\[0\]/)
  assert.match(source, /physicalDevice: filesystem\.physical_device \?\? filesystem\.device/)
  assert.match(source, /targetsByPhysicalDevice = new Map<string, Array<\{ mountpoint: string; physicalDevice: string \}>>\(\)/)
  assert.match(source, /targetsByPhysicalDevice\.get\(target\.physicalDevice\)/)
  assert.match(source, /const role = mountpoint === '\/' \? '系统盘' : '数据盘'/)
  assert.match(source, /class="disk-mount-card-role">\{\{ target\.role \}\}/)
  assert.match(source, /class="disk-mount-card-media">\{\{ target\.mediaLabel \}\}/)
  assert.match(source, /function diskMediaLabel\(mediaType: string \| undefined, interfaceType: string \| undefined\)/)
  assert.match(source, /mediaType === 'RAID'/)
  assert.match(source, /class="disk-mount-card-summary">\{\{ target\.device \}\} · \{\{ target\.size \}\} · \{\{ target\.mountpoint \}\}<\/span>/)
  assert.match(source, /\.disk-mount-card-grid\s*\{[\s\S]*?grid-template-columns:\s*repeat\(auto-fill, minmax\(280px, 320px\)\)/)
  assert.doesNotMatch(source, /target\.sharedLabel/)
  assert.match(source, /return mountpoint === '\/' \|\| isRecommendedDiskStressMountpoint\(mountpoint\)/)
  assert.match(source, /mountpoint\.startsWith\(prefix\)/)
  assert.match(source, /\['\/data', '\/mnt', '\/scratch', '\/public', '\/home', '\/root'\]/)
})

test('lets target server favorites be changed with vector stars without a warning background', async () => {
  const source = await readFile(new URL('./TaskRunner.vue', import.meta.url), 'utf8')

  assert.match(source, /import \{ Refresh, Star, StarFilled \} from '@element-plus\/icons-vue'/)
  assert.match(source, /<button\s+type="button"\s+class="s-card-star"\s+:class="\{ 'is-starred': starredServerIds\.includes\(server\.id\) \}"[\s\S]*?<StarFilled v-if="starredServerIds\.includes\(server\.id\)" \/>\s+<Star v-else \/>/)
  assert.match(source, /@click\.stop="toggleServerStar\(server\.id\)"/)
  assert.match(source, /function toggleServerStar\(serverId: number\)/)
  assert.match(source, /\['server-select-card', 'hpc-interactive-pulse', \{ 'is-active': selectedServerIds\.includes\(server\.id\), 'is-offline': server\.status === 'offline'/)
  assert.doesNotMatch(source, /\.server-select-card\.is-starred/)
  assert.doesNotMatch(source, /warning-light-[89]/)
  assert.doesNotMatch(source, /\? '★' : '☆'/)
})

test('probes every managed server before refreshing the target list', async () => {
  const source = await readFile(new URL('./TaskRunner.vue', import.meta.url), 'utf8')

  const probeFunction = source.match(/async function probeTargetServers\(\) \{([\s\S]*?)\n\}/)?.[1] ?? ''
  assert.match(source, /const probeTargetServersList = computed\(\(\) => managedServers\.value\)/)
  assert.match(probeFunction, /const targets = probeTargetServersList\.value/)
})

test('excludes archived servers from every task target group', async () => {
  const source = await readFile(new URL('./TaskRunner.vue', import.meta.url), 'utf8')

  assert.match(source, /const isArchivedServer = \(server: ServerRecord\) => server\.tags\?\.includes\('已归档服务器'\)/)
  assert.match(source, /const managedServers = computed\(\(\) => servers\.value[\s\S]*?filter\(\(server\) => !isArchivedServer\(server\)\)/)
  assert.match(source, /const filteredManagedServers = computed\(\(\) => \{[\s\S]*?managedServers\.value/)
  assert.match(source, /<el-tag size="small" :type="serverTagType\(t\.name\)">{{ t\.name }}<\/el-tag>/)
  assert.match(source, /sortTaskTags/)
  assert.match(source, /tags\.value = \(await listTags\(\)\)\.data\.items[\s\S]*?filter\(\(tag\) => tag\.name !== '已归档服务器'\)[\s\S]*?sort\(sortTaskTags\)/)
})

test('serializes structured monitor polling and waits for one response before scheduling the next', async () => {
  const source = await readFile(new URL('./TaskRunner.vue', import.meta.url), 'utf8')

  assert.match(source, /let monitorRequestInFlight = false/)
  assert.match(source, /if \(monitorRequestInFlight\) return/)
  assert.match(source, /monitorRequestInFlight = true/)
  assert.match(source, /monitorRequestInFlight = false/)
  assert.match(source, /monitorPollTimer = setTimeout\(\(\) => \{\s*void fetchMonitorData\(\)\s*\}, 5000\)/)
  assert.doesNotMatch(source, /monitorPollTimer = setInterval/)
})

test('describes the active GPU driver install policy instead of always showing the skip default', async () => {
  const source = await readFile(new URL('./TaskRunner.vue', import.meta.url), 'utf8')

  assert.match(source, /forceInstallIfDriverExists \? '将覆盖安装所选版本' : '默认检测到 nvidia-smi 后跳过安装。'/)
})

test('describes GPU driver installation as OS-aware rather than Rocky-only', async () => {
  const source = await readFile(new URL('./TaskRunner.vue', import.meta.url), 'utf8')

  assert.match(source, /自动识别 Rocky 9 或 Ubuntu：检查 GPU → 安装依赖 → 必要时禁用 Nouveau 并重启 → 安装 .run 驱动 → nvidia-smi 验证/)
  assert.doesNotMatch(source, /return 'Rocky 9\.4：检查 GPU/)
})
