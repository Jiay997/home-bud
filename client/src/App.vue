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

/* #ifdef H5 */
/* H5 无小程序原生 page 节点，token 需在 html/body 层兜底，
   保证自定义弹层、滚动容器等页面外节点同样继承配色与字体 */
html,
body {
  min-height: 100%;
  color: var(--ink-1);
  background-color: var(--bg);
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
}
/* 桌面宽屏下把应用限制在手机尺度内居中，避免 rpx 元素被无限拉伸 */
body {
  display: flex;
  justify-content: center;
  background-color: #E8E6E1;
}
uni-app {
  width: 100%;
  max-width: 480px;
  background-color: var(--bg);
  box-shadow: 0 0 24rpx rgba(46, 51, 46, .08);
}
/* 下拉刷新指示器为 absolute + width:100%，在桌面宽屏居中容器内会按视口宽度
   撑出横向滚动条；限制在应用容器宽度内，避免页面出现无意义的横向滑动 */
uni-page-refresh {
  width: 100%;
  max-width: 480px;
}
/* #endif */
</style>
