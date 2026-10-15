<script setup lang="ts">
import { useMediaImage } from '../services/use-media-image'

const props = withDefaults(defineProps<{
  kind: 'child' | 'pet'
  url?: string | null
  // 直径（rpx）；字形几何按 em 等比缩放，84（列表）与 152（详情）共用一套基准
  size?: number
  // 相机角标：可编辑提示，仅详情页头像使用
  badge?: boolean
  // 按压反馈：头像自身可点击时开启
  interactive?: boolean
}>(), { url: '', size: 84, badge: false, interactive: false })

// 直连失败（真机 http 图片限制）自动经 downloadFile 本地化重试，仍失败回退默认字形
const { src, showImage, onError } = useMediaImage(() => props.url || '')
</script>

<template>
  <view
    class="profile-avatar"
    :class="kind"
    :style="{ width: size + 'rpx', height: size + 'rpx', fontSize: size + 'rpx' }"
    :hover-class="interactive ? 'avatar-pressed' : 'none'"
  >
    <view class="avatar-circle">
      <image v-if="showImage" class="avatar-image" :src="src" mode="aspectFill" @error="onError" />
      <view v-else class="glyph" :class="kind === 'child' ? 'glyph-person' : 'glyph-paw'" />
    </view>
    <view v-if="badge" class="badge">
      <view class="camera">
        <view class="camera-body" />
        <view class="camera-lens" />
      </view>
    </view>
  </view>
</template>

<style scoped>
.profile-avatar { position: relative; flex: none; }
.avatar-pressed { opacity: .82; }

.avatar-circle { position: absolute; top: 0; right: 0; bottom: 0; left: 0; overflow: hidden; border-radius: 50%; }
.child .avatar-circle { background: var(--info-soft); }
.pet .avatar-circle { background: var(--warn-soft); }
.avatar-image { display: block; width: 100%; height: 100%; }

.glyph { position: absolute; top: 0; right: 0; bottom: 0; left: 0; }
.glyph-person::before { position: absolute; top: .238em; left: 50%; width: .19em; height: .19em; margin-left: -.131em; border: .036em solid var(--info); border-radius: 50%; content: ''; }
.glyph-person::after { position: absolute; top: .524em; left: 50%; width: .429em; height: .19em; margin-left: -.25em; border: .036em solid var(--info); border-bottom: 0; border-radius: .226em .226em 0 0; content: ''; }
.glyph-paw::before { position: absolute; top: .476em; left: .31em; width: .381em; height: .298em; background: var(--warn); border-radius: 50% 50% 45% 45% / 60% 60% 40% 40%; content: ''; }
.glyph-paw::after { position: absolute; top: .25em; left: .286em; width: .179em; height: .179em; background: var(--warn); border-radius: 50%; box-shadow: .262em .024em 0 var(--warn); content: ''; }

.badge { position: absolute; right: 0; bottom: .013em; display: flex; align-items: center; justify-content: center; width: .26em; height: .26em; background: var(--primary); border: .02em solid var(--surface); border-radius: 50%; box-sizing: border-box; }
.camera { position: relative; width: .155em; height: .145em; }
.camera-body { position: absolute; bottom: 0; left: 0; width: .155em; height: .11em; background: var(--surface); border-radius: .02em; }
.camera-body::before { position: absolute; top: -.028em; left: .042em; width: .07em; height: .035em; background: var(--surface); border-radius: .015em .015em 0 0; content: ''; }
.camera-lens { position: absolute; bottom: .0275em; left: .05em; width: .055em; height: .055em; background: var(--primary); border-radius: 50%; }
</style>
