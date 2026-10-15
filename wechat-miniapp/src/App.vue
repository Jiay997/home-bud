<script setup lang="ts">
import './uni.scss'
</script>

<style>
@import "./styles/texture.css";

page {
  min-height: 100%;
  color: var(--ink-1);
  background-color: var(--bg);
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
  /* C-2「织理质感」tokens（设计生成方案报告 §2） */
  --bg: #F4F3F0;
  --surface: #FFFFFF;
  --surface-warm: #FBF9F4;
  --ink-1: #2E332E;
  --ink-2: #5B625B;
  --ink-3: #8A9088;
  --line: #E3E2DE;
  --line-warm: #E8DFCE;
  --primary: #7C9082;
  --primary-press: #67796D;
  --primary-soft: #E4EBE3;
  --info: #8FA6BC;
  --info-soft: #E2EAF2;
  --warn: #C08A50;
  --warn-soft: #F5E9D8;
  --danger: #B4756C;
  --danger-soft: #F2E2DF;
  --on-primary: #FFFFFF;
  --r-card: 24rpx;
  --r-control: 999rpx;
  --r-inner: 16rpx;
  --shadow-card: 0 8rpx 24rpx rgba(46, 51, 46, .06);
  --shadow-float: 0 16rpx 48rpx rgba(46, 51, 46, .12);
  --border-warm: 1rpx solid #E8DFCE;
}
button {
  color: var(--ink-1);
  background: transparent;
}
button::after {
  border: none;
}
</style>
