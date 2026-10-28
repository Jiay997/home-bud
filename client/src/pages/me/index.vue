<template>
  <view class="me-page tex">
    <MiniPageHeader :title="pageTitle" />

    <view class="page-body">
      <StateSkeleton v-if="state === 'loading'" mode="skeleton" />
      <StateSkeleton
        v-else-if="state === 'error'"
        mode="empty"
        :title="errorTitle"
        :copy="errorMessage"
        :action-text="retryCopy"
        @action="load(true)"
      />

      <template v-else>
        <view class="user-card">
          <view class="user-avatar" aria-hidden="true">
            <image
              v-if="showAvatarImage"
              class="user-avatar-img"
              :src="avatarSrc"
              mode="aspectFill"
              @error="onAvatarError"
            />
            <view v-else class="glyph glyph-person-lg" />
          </view>
          <view class="user-main">
            <view class="user-name-row">
              <text class="user-name">{{ displayName }}</text>
              <button class="edit-pill" hover-class="pressed" @tap="openProfileSheet">{{ editPill }}</button>
            </view>
            <text class="user-uid">{{ uidLine }}</text>
          </view>
        </view>
        <view class="member-band tex" :class="memberBandTone" hover-class="pressed" @tap="memberCardTap">
          <text class="member-text">{{ memberLine }}</text>
          <view v-if="memberRetryHint" class="member-pill"><text>{{ memberRetryHint }}</text></view>
        </view>

        <text class="group-title">{{ groupArchive }}</text>
        <view class="menu-card">
          <view class="card-row" hover-class="row-pressed" @tap="goProfiles">
            <view class="row-icon icon-info"><view class="glyph glyph-child" /></view>
            <view class="row-main">
              <text class="row-title">{{ rowChild }}</text>
            </view>
            <text class="row-value">{{ childCountText }}</text>
            <view class="row-arrow" />
          </view>
          <view class="card-row" hover-class="row-pressed" @tap="goProfiles">
            <view class="row-icon icon-warn"><view class="glyph glyph-pet" /></view>
            <view class="row-main">
              <text class="row-title">{{ rowPet }}</text>
            </view>
            <text class="row-value">{{ petCountText }}</text>
            <view class="row-arrow" />
          </view>
        </view>

        <text class="group-title">{{ groupCare }}</text>
        <view class="menu-card">
          <view class="card-row" hover-class="row-pressed" @tap="goHealth">
            <view class="row-icon icon-primary"><view class="glyph glyph-record" /></view>
            <view class="row-main">
              <text class="row-title">{{ rowHealth }}</text>
            </view>
            <text class="row-value">{{ enterValue }}</text>
            <view class="row-arrow" />
          </view>
          <view class="card-row" hover-class="row-pressed" @tap="goNotes">
            <view class="row-icon icon-info"><view class="glyph glyph-doc" /></view>
            <view class="row-main">
              <text class="row-title">{{ rowNotes }}</text>
            </view>
            <text class="row-value">{{ enterValue }}</text>
            <view class="row-arrow" />
          </view>
          <view class="card-row" hover-class="row-pressed" @tap="goReminders">
            <view class="row-icon icon-primary"><view class="glyph glyph-record" /></view>
            <view class="row-main">
              <text class="row-title">{{ rowReminders }}</text>
            </view>
            <text class="row-value">{{ enterValue }}</text>
            <view class="row-arrow" />
          </view>
        </view>

        <text class="group-title">{{ groupRecords }}</text>
        <view class="menu-card">
          <view class="card-row" hover-class="row-pressed" @tap="goRecords">
            <view class="row-icon icon-primary"><view class="glyph glyph-record" /></view>
            <view class="row-main">
              <text class="row-title">{{ rowHistory }}</text>
            </view>
            <text class="row-value">{{ historyValue }}</text>
            <view class="row-arrow" />
          </view>
          <view class="card-row" hover-class="row-pressed" @tap="openSheet('feedback')">
            <view class="row-icon icon-primary"><view class="glyph glyph-feedback" /></view>
            <view class="row-main">
              <text class="row-title">{{ rowFeedback }}</text>
            </view>
            <text class="row-value">{{ submitValue }}</text>
            <view class="row-arrow" />
          </view>
        </view>

        <text class="group-title">{{ groupMember }}</text>
        <view class="menu-card">
          <view class="card-row" hover-class="row-pressed" @tap="openMember">
            <view class="row-icon icon-warn"><view class="glyph glyph-member" /></view>
            <view class="row-main">
              <text class="row-title">{{ rowMember }}</text>
            </view>
            <text class="row-value">{{ memberRowValue }}</text>
            <view class="row-arrow" />
          </view>
        </view>

        <text class="group-title">{{ groupRights }}</text>
        <view class="menu-card">
          <view class="card-row" hover-class="row-pressed" @tap="openSheet('rights')">
            <view class="row-icon icon-info"><view class="glyph glyph-shield" /></view>
            <view class="row-main">
              <text class="row-title">{{ rowRights }}</text>
            </view>
            <text class="row-value">{{ enterValue }}</text>
            <view class="row-arrow" />
          </view>
          <view class="card-row" hover-class="row-pressed" @tap="goPrivacyPledge">
            <view class="row-icon icon-info"><view class="glyph glyph-shield" /></view>
            <view class="row-main">
              <text class="row-title">{{ rowPrivacyPledge }}</text>
            </view>
            <text class="row-value">{{ viewValue }}</text>
            <view class="row-arrow" />
          </view>
          <view class="card-row" hover-class="row-pressed" @tap="openDoc('childRule')">
            <view class="row-icon icon-info"><view class="glyph glyph-doc" /></view>
            <view class="row-main">
              <text class="row-title">{{ rowChildRule }}</text>
            </view>
            <text class="row-value">{{ viewValue }}</text>
            <view class="row-arrow" />
          </view>
          <view class="card-row" hover-class="row-pressed" @tap="openDoc('sharing')">
            <view class="row-icon icon-info"><view class="glyph glyph-link" /></view>
            <view class="row-main">
              <text class="row-title">{{ rowSharing }}</text>
            </view>
            <text class="row-value">{{ viewValue }}</text>
            <view class="row-arrow" />
          </view>
        </view>

        <text class="group-title">{{ groupTerms }}</text>
        <view class="menu-card">
          <view class="card-row">
            <view class="row-icon icon-primary"><view class="glyph glyph-terms" /></view>
            <view class="row-main term-links">
              <text class="inline-link" @tap="openDoc('agreement')">{{ linkAgreement }}</text>
              <text class="inline-dot">·</text>
              <text class="inline-link" @tap="openDoc('policy')">{{ linkPolicy }}</text>
              <text class="inline-dot">·</text>
              <text class="inline-link" @tap="openDoc('disclaimer')">{{ linkDisclaimer }}</text>
            </view>
          </view>
          <view class="card-row" hover-class="row-pressed" @tap="openDoc('aiNote')">
            <view class="row-icon icon-primary"><view class="glyph glyph-ai" /></view>
            <view class="row-main">
              <text class="row-title">{{ aiNoteTitle }}</text>
            </view>
            <text class="row-value">{{ viewValue }}</text>
            <view class="row-arrow" />
          </view>
        </view>

        <text class="group-title">{{ groupAccount }}</text>
        <view class="menu-card">
          <view class="card-row" hover-class="row-pressed" @tap="openSheet('account')">
            <view class="row-icon icon-primary"><view class="glyph glyph-person" /></view>
            <view class="row-main">
              <text class="row-title">{{ rowAccount }}</text>
            </view>
            <text class="row-value">{{ enterValue }}</text>
            <view class="row-arrow" />
          </view>
        </view>

        <text class="footer-note">{{ footerNote }}</text>
      </template>
    </view>

    <template v-if="state === 'ready'">
      <MiniComplianceBar fixed />
      <MiniTabBar active="me" />
    </template>

    <view v-if="sheet.visible" class="sheet-mask" @tap="closeSheet">
      <view class="sheet" @tap.stop>
        <view class="sheet-head">
          <text class="sheet-title">{{ sheetTitle }}</text>
          <button class="sheet-close" hover-class="pressed" @tap="closeSheet">{{ closeCopy }}</button>
        </view>

        <scroll-view v-if="sheet.kind === 'feedback'" scroll-y class="sheet-scroll">
          <text class="sheet-caption">{{ feedbackCaption }}</text>
          <textarea
            class="feedback-input"
            v-model="feedbackText"
            maxlength="2000"
            placeholder="写下遇到的问题或建议"
            placeholder-class="field-placeholder"
            :auto-height="true"
          />
          <text class="sheet-note">{{ feedbackNote }}</text>
          <view class="sheet-gap" />
        </scroll-view>

        <scroll-view v-else-if="sheet.kind === 'rights'" scroll-y class="sheet-scroll">
          <text class="sheet-caption">{{ rightsSlaCopy }}</text>
          <view class="sheet-list">
            <view v-for="entry in rightsEntries" :key="entry.key" class="list-row">
              <view class="list-main">
                <text class="list-title">{{ entry.title }}</text>
                <text class="list-sub">{{ entry.sub }}</text>
              </view>
              <button class="action-pill" :class="{ disabled: rightsBusy }" :disabled="rightsBusy" hover-class="pressed" @tap="entry.run">{{ entry.action }}</button>
            </view>
          </view>

          <text class="sheet-section">{{ requestsTitle }}</text>
          <view v-if="rightsLoading" class="list-note">
            <text class="list-sub">{{ requestsLoadingCopy }}</text>
          </view>
          <view v-else-if="rightsError" class="list-note">
            <text class="note-error">{{ rightsError }}</text>
            <button class="mini-link" hover-class="pressed" @tap="loadRights">{{ retryCopy }}</button>
          </view>
          <view v-else-if="!rightsItems.length" class="list-note">
            <text class="list-sub">{{ requestsEmpty }}</text>
          </view>
          <view v-else class="sheet-list">
            <view v-for="item in rightsItems" :key="item.request_no" class="request-row">
              <view class="request-head">
                <text class="list-title">{{ requestTypeLabel(item.request_type) }}</text>
                <text class="request-status" :class="statusTone(item.status)">{{ requestStatusLabel(item.status) }}</text>
              </view>
              <text class="list-sub">{{ requestMeta(item) }}</text>
              <text v-if="item.status === 'rejected'" class="request-reject">{{ rejectReasonLabel(item) }}</text>
              <button v-if="canDownload(item)" class="mini-link" hover-class="pressed" @tap="downloadExport(item.request_no)">{{ downloadCopy }}</button>
              <text class="request-no">{{ item.request_no }}</text>
            </view>
          </view>
          <view class="sheet-gap" />
        </scroll-view>

        <scroll-view v-else-if="sheet.kind === 'account'" scroll-y class="sheet-scroll">
          <view class="sheet-list">
            <view class="list-row">
              <view class="list-main"><text class="list-title">账户标识</text></view>
              <text class="list-value">{{ shortUid }}</text>
            </view>
            <view class="list-row">
              <view class="list-main"><text class="list-title">登录方式</text></view>
              <text class="list-value">{{ loginMethodCopy }}</text>
            </view>
            <view class="list-row">
              <view class="list-main"><text class="list-title">注册时间</text></view>
              <text class="list-value">{{ registerText || noneCopy }}</text>
            </view>
          </view>

          <text class="sheet-section">账号管理</text>
          <text class="sheet-caption">{{ accountManageCaption }}</text>
          <view class="sheet-list">
            <view class="list-row">
              <view class="list-main">
                <text class="list-title">{{ logoutTitle }}</text>
                <text class="list-sub">{{ logoutSub }}</text>
              </view>
              <button class="action-pill" hover-class="pressed" @tap="askSignOut(false)">{{ logoutAction }}</button>
            </view>
            <view class="list-row">
              <view class="list-main">
                <text class="list-title">{{ switchTitle }}</text>
                <text class="list-sub">{{ switchSub }}</text>
              </view>
              <button class="action-pill" hover-class="pressed" @tap="askSignOut(true)">{{ switchAction }}</button>
            </view>
          </view>

          <text class="sheet-section">撤回同意（分项）</text>
          <text class="sheet-caption">{{ withdrawCaption }}</text>
          <view class="sheet-list">
            <view class="list-row">
              <view class="list-main">
                <text class="list-title">基础同意</text>
                <text class="list-sub">{{ consentBase ? agreedCopy : notAgreedCopy }}</text>
              </view>
              <button v-if="consentBase" class="action-pill danger-pill" :class="{ disabled: withdrawBusy }" :disabled="withdrawBusy" hover-class="pressed" @tap="askWithdraw(baseConsentType)">{{ withdrawCopy }}</button>
            </view>
            <view class="list-row">
              <view class="list-main">
                <text class="list-title">儿童信息单独同意</text>
                <text class="list-sub">{{ consentChild ? agreedCopy : notAgreedCopy }}</text>
              </view>
              <button v-if="consentChild" class="action-pill danger-pill" :class="{ disabled: withdrawBusy }" :disabled="withdrawBusy" hover-class="pressed" @tap="askWithdraw(childConsentType)">{{ withdrawCopy }}</button>
            </view>
          </view>

          <text class="sheet-section">账号注销</text>
          <text class="sheet-caption">{{ deactivateCaption }}</text>
          <button class="danger-button" :class="{ disabled: rightsBusy }" :disabled="rightsBusy" hover-class="pressed" @tap="deactivateFlow">{{ deactivateCopy }}</button>
          <view class="sheet-gap" />
        </scroll-view>

        <scroll-view v-else-if="sheet.kind === 'profile'" scroll-y class="sheet-scroll">
          <text class="sheet-caption">{{ profileCaption }}</text>
          <view class="profile-head" hover-class="pressed" @tap="pickAvatar">
            <view class="profile-avatar">
              <image
                v-if="showAvatarImage"
                class="profile-avatar-img"
                :src="avatarSrc"
                mode="aspectFill"
                @error="onAvatarError"
              />
              <view v-else class="glyph glyph-person-lg" />
            </view>
            <view class="profile-head-main">
              <text class="list-title">账号头像</text>
              <text class="list-sub">{{ avatarBusy ? avatarUploadingCopy : avatarHint }}</text>
            </view>
            <text class="profile-action">{{ avatarBusy ? avatarUploadingCopy : avatarChangeCopy }}</text>
          </view>
          <button v-if="me?.avatar_url" class="mini-link" hover-class="pressed" @tap="removeAvatar">{{ avatarRemoveCopy }}</button>

          <text class="sheet-section">{{ nicknameTitle }}</text>
          <input
            class="profile-input"
            v-model="nicknameDraft"
            :maxlength="nicknameMaxLength"
            :placeholder="nicknamePlaceholder"
            placeholder-class="field-placeholder"
          />
          <text class="sheet-note">{{ nicknameNote }}</text>
          <text v-if="profileError" class="profile-error">{{ profileError }}</text>
          <view class="sheet-gap" />
        </scroll-view>

        <scroll-view v-else-if="sheet.kind === 'overview'" scroll-y class="sheet-scroll">
          <view class="sheet-list">
            <view class="list-row">
              <view class="list-main"><text class="list-title">孩子档案</text></view>
              <text class="list-value">{{ childCountText }}</text>
            </view>
            <view class="list-row">
              <view class="list-main"><text class="list-title">宠物档案</text></view>
              <text class="list-value">{{ petCountText }}</text>
            </view>
            <view class="list-row">
              <view class="list-main"><text class="list-title">观察与问答记录</text></view>
              <text class="list-value">{{ historyTotal === null ? '暂不可用' : historyValue }}</text>
            </view>
            <view class="list-row">
              <view class="list-main"><text class="list-title">基础同意</text></view>
              <text class="list-value">{{ consentBase ? agreedCopy : notAgreedCopy }}</text>
            </view>
            <view class="list-row">
              <view class="list-main"><text class="list-title">儿童信息单独同意</text></view>
              <text class="list-value">{{ consentChild ? agreedCopy : notAgreedCopy }}</text>
            </view>
          </view>
          <text class="sheet-note">{{ overviewNote }}</text>
          <view class="sheet-gap" />
        </scroll-view>

        <scroll-view v-else scroll-y class="sheet-scroll">
          <text v-for="(para, index) in currentDocParagraphs" :key="index" class="doc-para">{{ para }}</text>
          <view class="sheet-gap" />
        </scroll-view>

        <view v-if="sheet.kind === 'feedback'" class="sheet-actions">
          <button class="primary-button" :class="{ disabled: !feedbackText.trim() || feedbackBusy }" :disabled="!feedbackText.trim() || feedbackBusy" hover-class="pressed" @tap="submitFeedback">{{ feedbackBusy ? feedbackBusyCopy : feedbackSubmitCopy }}</button>
          <button class="ghost-button" hover-class="pressed" @tap="closeSheet">{{ cancelCopy }}</button>
        </view>
        <view v-else-if="sheet.kind === 'profile'" class="sheet-actions">
          <button class="primary-button" :class="{ disabled: profileBusy }" :disabled="profileBusy" hover-class="pressed" @tap="saveProfile">{{ profileBusy ? profileSavingCopy : profileSaveCopy }}</button>
          <button class="ghost-button" hover-class="pressed" @tap="closeSheet">{{ cancelCopy }}</button>
        </view>
      </view>
    </view>

    <MiniDialog
      :visible="dialog.visible"
      :title="dialog.title"
      :message="dialog.message"
      :confirm-text="dialog.confirmText"
      :cancel-text="dialog.cancelText"
      :show-cancel="dialog.showCancel"
      :danger="dialog.danger"
      :input="dialog.input"
      @confirm="onDialogConfirm"
      @cancel="onDialogCancel"
    />
    <MiniActionSheet
      :visible="actionSheet.visible"
      :items="actionSheet.items"
      @select="onActionSheetSelect"
      @close="onActionSheetClose"
    />
  </view>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { onLoad, onPullDownRefresh, onShow } from '@dcloudio/uni-app'
import { api, TOKEN_KEY, mediaUrl, type MeView } from '../../api'
import MiniPageHeader from '../../components/MiniPageHeader.vue'
import MiniTabBar from '../../components/MiniTabBar.vue'
import MiniComplianceBar from '../../components/MiniComplianceBar.vue'
import MiniDialog from '../../components/MiniDialog.vue'
import MiniActionSheet from '../../components/MiniActionSheet.vue'
import StateSkeleton from '../../components/StateSkeleton.vue'
import { useActionSheet, useDialog } from '../../services/dialog'
import { ensureBaseConsent, signOut } from '../../services/session'
import { decodeRouteValue } from '../../services/route'
import { useMediaImage } from '../../services/use-media-image'
import { userFacingMessage } from '../../services/user-message'
import { isMiniProgram, runtime } from '../../platform/runtime'

type SheetKind = 'feedback' | 'rights' | 'account' | 'overview' | 'profile' | 'doc'
type DocKey = 'childRule' | 'sharing' | 'aiNote' | 'agreement' | 'policy' | 'disclaimer'
type RightsItem = {
  request_no: string
  request_type: string
  status: string
  sla_due_at: string | null
  reject_reason_code: string | null
  created_at: string | null
  handled_at: string | null
}

const pageTitle = '我的'
const errorTitle = '账户信息暂时无法打开'
const retryCopy = '重新加载'
const closeCopy = '关闭'
const cancelCopy = '取消'
const footerNote = '观察帮助理解，不给家庭贴标签。'
const userRoleTitle = '家长用户'
const editPill = '编辑'
const loginMethodCopy = '微信小程序登录'
// 账号资料编辑
const sheetProfileTitle = '编辑账号资料'
const profileCaption = '头像更换后立即生效；昵称需点击「保存」后生效，二者仅影响本账号的资料展示。'
const avatarHint = '点击更换，支持 jpg / png / webp'
const avatarChangeCopy = '更换'
const avatarUploadingCopy = '正在上传…'
const avatarRemoveCopy = '移除头像'
const avatarUpdatedCopy = '头像已更新'
const avatarUploadFailedCopy = '头像上传失败，请稍后重试。'
const avatarPickFailedCopy = '无法打开相册或相机，请检查权限后重试。'
const avatarRemovedCopy = '头像已移除'
const avatarRemoveFailedCopy = '头像移除失败，请稍后重试。'
const nicknameTitle = '昵称'
const nicknamePlaceholder = '请输入昵称'
const nicknameNote = '1-20 个字符，保存后「我的」页面立即更新。'
const nicknameEmptyCopy = '昵称不能为空，请先填写。'
const profileSaveCopy = '保存'
const profileSavingCopy = '正在保存…'
const profileSavedCopy = '资料已保存'
const profileSaveFailedCopy = '资料保存失败，请稍后重试。'
const nicknameMaxLength = 20
// 账号管理
const accountManageCaption = '退出登录仅清除本机登录状态；切换账号会退出当前账号并按新的登录身份重新加载数据。'
const logoutTitle = '退出登录'
const logoutSub = '清除本机登录凭证与账号缓存，服务端数据保留；下次进入需重新登录当前账号。'
const logoutAction = '退出'
const logoutConfirmTitle = '退出登录'
const logoutConfirmCopy = '将清除本机登录凭证与账号缓存；服务端数据不受影响。退出后首页会显示登录入口，登录成功仍进入当前账号。'
const switchTitle = '切换账号'
const switchAction = '切换'
const switchSubMini = '退出当前账号并重新获取微信登录身份；登录后按该微信对应的账号加载数据。'
const switchSubDev = '退出当前账号并清除本机设备身份，重新登录会进入一个独立的新账号；原账号数据仍保留在服务端。'
const switchConfirmTitle = '切换账号'
const switchConfirmCopyMini = '将退出当前账号并清除本机登录状态。微信小程序登录以当前微信身份为准，如需使用其他账号，请先在微信客户端切换账号，再回到小程序完成登录。'
const switchConfirmCopyDev = '将退出当前账号并清除本机设备身份。重新登录会创建一个独立的新账号，本机将无法直接切回原账号，但原账号数据仍保留在服务端。'
const noneCopy = '未记录'
const agreedCopy = '已同意'
const notAgreedCopy = '未同意'
const withdrawCopy = '撤回'
const submitValue = '提交'
const enterValue = '进入'
const viewValue = '查看'
const baseConsentType = 'base'
const childConsentType = 'child_personal_info'

const groupArchive = '档案'
const groupCare = '健康与笔记'
const groupRecords = '记录'
const groupMember = '会员'
const groupRights = '个人信息权利'
const groupTerms = '协议与声明'
const groupAccount = '账号'
const rowChild = '孩子档案'
const rowPet = '宠物档案'
const rowHealth = '健康档案'
const rowNotes = '我的笔记'
const rowReminders = '提醒设置'
const rowHistory = '历史问答与报告'
const rowFeedback = '意见反馈'
const rowMember = '会员与订单'
const rowRights = '个人信息权利中心'
const rowPrivacyPledge = '隐私承诺'
const rowChildRule = '儿童信息处理规则（易懂版）'
const rowSharing = '第三方共享清单'
const aiNoteTitle = 'AI 生成内容标识说明'
const rowAccount = '账号与安全'
const linkAgreement = '用户协议'
const linkPolicy = '隐私政策'
const linkDisclaimer = '免责声明'

const sheetFeedbackTitle = '意见反馈'
const sheetRightsTitle = '个人信息权利中心'
const sheetAccountTitle = '账号与安全'
const sheetOverviewTitle = '查阅我的信息'
const feedbackCaption = '请描述遇到的问题或建议，提交后会获得受理编号与处置时限。'
const feedbackNote = '也可以附上问题发生的场景，便于我们更快定位。'
const feedbackSubmitCopy = '提交反馈'
const feedbackBusyCopy = '正在提交…'

const rightsSlaCopy = '六类权利请求统一在本页管理，承诺 15 个工作日内答复；被拒绝时会说明原因。'
const requestsTitle = '申请记录'
const requestsLoadingCopy = '正在读取申请记录…'
const requestsEmpty = '暂无申请记录，提交后可在本页查看进度。'
const downloadCopy = '下载导出文件'

const withdrawCaption = '撤回后停止处理对应信息；基础同意撤回后仍可浏览通用内容与宠物模块。'
const withdrawBaseNote = '撤回基础同意后将停止提供个性化回答与测评；仍可浏览通用内容与宠物模块，可随时重新同意。'
const withdrawChildNote = '撤回儿童信息单独同意后，孩子档案将停用、不再写入新数据；撤回前已完成的处理不受影响。'
const deactivateCaption = '注销后数据删除、不可恢复；订单与交易记录按法定义务留存。'
const deactivateCopy = '注销账号'

const overviewNote = '如需完整明细，可提交「复制与导出」申请，生成后在本页下载。'

const docTitles: Record<DocKey, string> = {
  childRule: rowChildRule,
  sharing: rowSharing,
  aiNote: aiNoteTitle,
  agreement: linkAgreement,
  policy: linkPolicy,
  disclaimer: linkDisclaimer
}
const docParagraphs: Record<DocKey, string[]> = {
  childRule: [
    '我们只为生成养育参考收集必需的儿童信息：昵称、出生日期、性别、身高体重、早产标记、过敏项与辅食月龄。',
    '这些信息加密存储，仅用于为你生成贴合月龄的建议，不用于模型训练，也不会出售给任何第三方。',
    '你可以随时在「我的 - 账号与安全」撤回儿童信息单独同意；撤回后孩子档案停用、不再写入新数据，撤回前已完成的处理不受影响。',
    '正式文本与版本更新以公布的《儿童个人信息处理规则》为准。'
  ],
  sharing: [
    '当前版本不会将你的个人信息共享给第三方用于营销或广告。',
    '生成回答时，相关信息仅在加密通道内用于本次推理，不对外留存。',
    '如未来涉及第三方共享，我们会更新本清单并公示；重大变更将重新征得你的同意。'
  ],
  aiNote: [
    '你在本服务中看到的回应、报告与建议，均由人工智能模型生成。',
    '内容仅作为家庭养育与共居参考，不构成医疗、心理、兽医等专业意见或诊断。',
    '涉及健康与安全的问题，请咨询具备资质的专业人员；如有紧急情况，请及时就医。'
  ],
  agreement: [
    '欢迎使用Babe宝伴。使用本服务前，请了解以下要点。',
    '本服务为家庭养育与宠物共居提供参考信息，不替代专业人员意见。',
    '请勿利用本服务提交违法违规内容；违规使用可能导致服务受限。',
    '正式《用户协议》文本将在上线前公布，届时以正式版本为准。'
  ],
  policy: [
    'Babe宝伴仅处理你主动提交的信息：咨询问题、档案信息、测评回答与反馈内容。',
    '信息用于生成回答与报告、保障服务与合规安全；儿童信息加密存储并单独同意。',
    '你可以在「个人信息权利中心」查阅、更正、导出、删除你的信息，或撤回同意。',
    '正式《隐私政策》文本将在上线前公布，届时以正式版本为准。'
  ],
  disclaimer: [
    '本服务中的内容由人工智能生成，仅供参考。',
    '不构成医疗、心理、兽医等专业意见、诊断或治疗方案。',
    '请结合孩子的实际情况与专业人员意见做判断；如有异常，请及时就医或咨询专业人士。'
  ]
}

const rightsTypeLabels: Record<string, string> = {
  access: '查阅信息',
  correct: '更正信息',
  export: '复制与导出',
  withdraw: '撤回同意',
  delete: '删除信息',
  deactivate: '账号注销'
}
const rightsStatusLabels: Record<string, string> = {
  submitted: '处理中',
  exported: '可下载',
  done: '已完成',
  rejected: '已拒绝'
}

const state = ref<'loading' | 'error' | 'ready'>('loading')
const errorMessage = ref('连接失败，请检查网络后重试。')
const me = ref<MeView | null>(null)
const isMember = ref(false)
const memberExpireText = ref('')
const historyTotal = ref<number | null>(null)
const consentBase = ref(false)
const consentChild = ref(false)
const loading = ref(false)
// 外部跳转带入的区块（隐私承诺页的可操作跳转：rights=权利中心 / consents=同意记录）
const pendingSection = ref('')

const sheet = reactive({ visible: false, kind: 'feedback' as SheetKind })
const docKey = ref<DocKey>('childRule')
const feedbackText = ref('')
const feedbackBusy = ref(false)
const rightsItems = ref<RightsItem[]>([])
const rightsLoading = ref(false)
const rightsError = ref('')
const rightsBusy = ref(false)
const withdrawBusy = ref(false)
// 账号资料编辑态：昵称草稿独立于 me，取消编辑不影响已保存值
const nicknameDraft = ref('')
const profileBusy = ref(false)
const avatarBusy = ref(false)
const profileError = ref('')
const { dialog, openDialog, onDialogConfirm, onDialogCancel } = useDialog()
const { actionSheet, openActionSheet, onActionSheetSelect, onActionSheetClose } = useActionSheet()

// 微信正式环境按微信身份切换账号；开发态/H5 按设备身份切换
const isWeChatAuth = isMiniProgram && !import.meta.env.DEV
const switchSub = computed(() => (isWeChatAuth ? switchSubMini : switchSubDev))
const switchConfirmCopy = computed(() => (isWeChatAuth ? switchConfirmCopyMini : switchConfirmCopyDev))
const displayName = computed(() => me.value?.nickname?.trim() || userRoleTitle)
const avatarUrl = computed(() => (me.value?.avatar_url ? mediaUrl(me.value.avatar_url) : ''))
const { src: avatarSrc, showImage: showAvatarImage, onError: onAvatarError } = useMediaImage(() => avatarUrl.value)

const childLimit = computed(() => (isMember.value ? 10 : 3))
const petLimit = computed(() => (isMember.value ? 10 : 3))
const shortUid = computed(() => {
  const uid = me.value?.user_uid || '未登录'
  return uid.length > 18 ? `${uid.slice(0, 18)}…` : uid
})
const uidLine = computed(() => `账户标识 ${shortUid.value}`)
const childCountText = computed(() => `${me.value?.child_profile_count ?? 0} / ${childLimit.value}`)
const petCountText = computed(() => `${me.value?.pet_profile_count ?? 0} / ${petLimit.value}`)
const historyValue = computed(() => (historyTotal.value === null ? '' : `共 ${historyTotal.value} 条`))
const registerText = computed(() => {
  const value = me.value?.register_at
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return `注册于 ${String(value).slice(0, 10)}`
  return `注册于 ${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
})

const memberLine = computed(() => {
  if (isMember.value) {
    return memberExpireText.value ? `会员 · 有效期至 ${memberExpireText.value}` : '会员状态获取失败，点此重试'
  }
  return '未开通会员 · 去开通'
})
const memberBandTone = computed(() => {
  if (!isMember.value) return 'tone-free'
  return memberExpireText.value ? 'tone-active' : 'tone-unknown'
})
const memberRetryHint = computed(() => (isMember.value && !memberExpireText.value ? retryCopy : ''))
const memberRowValue = computed(() => {
  if (!isMember.value) return '未开通'
  return memberExpireText.value || '已开通'
})
const sheetTitle = computed(() => {
  if (sheet.kind === 'feedback') return sheetFeedbackTitle
  if (sheet.kind === 'rights') return sheetRightsTitle
  if (sheet.kind === 'account') return sheetAccountTitle
  if (sheet.kind === 'overview') return sheetOverviewTitle
  if (sheet.kind === 'profile') return sheetProfileTitle
  return docTitles[docKey.value]
})
const currentDocParagraphs = computed(() => docParagraphs[docKey.value])

const rightsEntries: { key: string; title: string; sub: string; action: string; run: () => void }[] = [
  { key: 'access', title: '查阅我的信息', sub: '档案、问答、报告与同意记录', action: '查看', run: openOverview },
  { key: 'correct', title: '更正信息', sub: '档案可自助修改；记录类信息可提交申请', action: '申请', run: requestCorrect },
  { key: 'export', title: '复制与导出', sub: '导出文件生成后可下载，链接 24 小时内有效', action: '导出', run: requestExport },
  { key: 'withdraw', title: '撤回同意（分项）', sub: '基础同意 / 儿童信息单独同意', action: '撤回', run: withdrawFlow },
  { key: 'delete', title: '删除个人信息', sub: '删除后不可恢复；交易记录按法定义务留存', action: '提交', run: requestDelete },
  { key: 'deactivate', title: '账号注销', sub: '提交后进入注销流程，操作不可恢复', action: '注销', run: deactivateFlow }
]

function applyMember(status: string | null | undefined, expireAt: string | null | undefined) {
  const expireMs = expireAt ? new Date(expireAt).getTime() : 0
  isMember.value = status === 'member' && (!expireMs || expireMs > Date.now())
  memberExpireText.value = isMember.value && expireAt ? String(expireAt).slice(0, 10) : ''
}

function requestTypeLabel(value: string) {
  return rightsTypeLabels[value] || '权利请求'
}
function requestStatusLabel(value: string) {
  return rightsStatusLabels[value] || '处理中'
}
function statusTone(value: string) {
  if (value === 'done') return 'tone-done'
  if (value === 'rejected') return 'tone-reject'
  if (value === 'exported') return 'tone-ok'
  return 'tone-wait'
}
function requestMeta(item: RightsItem) {
  const parts: string[] = []
  if (item.created_at) parts.push(`提交于 ${String(item.created_at).slice(0, 10)}`)
  if (item.status === 'done' && item.handled_at) {
    parts.push(`完成于 ${String(item.handled_at).slice(0, 10)}`)
  } else if (item.sla_due_at && item.status !== 'rejected') {
    parts.push(`预计 ${String(item.sla_due_at).slice(0, 10)} 前答复`)
  }
  return parts.join(' · ')
}
function rejectReasonLabel(item: RightsItem) {
  const code = item.reject_reason_code ? `（${item.reject_reason_code}）` : ''
  return `未通过${code}：可补充材料后重新提交，或通过意见反馈联系我们。`
}
function canDownload(item: RightsItem) {
  return item.request_type === 'export' && item.status === 'exported'
}

async function load(showLoading = false) {
  if (showLoading) state.value = 'loading'
  if (loading.value) return
  loading.value = true
  errorMessage.value = ''
  try {
    if (!(await ensureBaseConsent())) {
      uni.reLaunch({ url: '/pages/index/index' })
      return
    }
    const [meResult, consentResult, subResult, historyResult] = await Promise.allSettled([
      api.me(),
      api.myConsents(),
      api.subscription(),
      api.history({ page: 1, page_size: 1 })
    ])
    if (meResult.status === 'rejected') throw meResult.reason
    me.value = meResult.value
    applyMember(meResult.value.member_status, meResult.value.member_expire_at)
    if (subResult.status === 'fulfilled') {
      applyMember(subResult.value.member_status, subResult.value.member_expire_at)
    }
    if (consentResult.status === 'fulfilled') {
      const consents = consentResult.value.consents || {}
      consentBase.value = Boolean(consents.base)
      consentChild.value = Boolean(consents.child_personal_info)
    }
    historyTotal.value = historyResult.status === 'fulfilled' ? historyResult.value.total : null
    state.value = 'ready'
    applyPendingSection()
  } catch (error: any) {
    if (state.value === 'ready') {
      uni.showToast({ title: userFacingMessage(error, '刷新失败，请稍后重试。'), icon: 'none' })
    } else {
      errorMessage.value = userFacingMessage(error, '连接失败，请检查网络后重试。')
      state.value = 'error'
    }
  } finally {
    loading.value = false
    uni.stopPullDownRefresh()
  }
}

async function refreshConsents() {
  try {
    const result = await api.myConsents()
    const consents = result.consents || {}
    consentBase.value = Boolean(consents.base)
    consentChild.value = Boolean(consents.child_personal_info)
  } catch {
    // 刷新失败时保留本地状态
  }
}

function goProfiles() {
  uni.redirectTo({ url: '/pages/profiles/index' })
}
function goHealth() {
  uni.navigateTo({ url: '/pages/health/index' })
}
function goNotes() {
  uni.navigateTo({ url: '/pages/notes/index' })
}
function goRecords() {
  uni.redirectTo({ url: '/pages/records/index' })
}
function goPrivacyPledge() {
  uni.navigateTo({ url: '/pages/privacy-pledge/index' })
}
function goReminders() {
  uni.navigateTo({ url: '/pages/reminders/index' })
}
function openMember() {
  uni.navigateTo({ url: '/pages/member/index' })
}
function memberCardTap() {
  if (isMember.value && !memberExpireText.value) {
    void load()
    return
  }
  openMember()
}
/**
 * 打开账号资料编辑面板：以已保存昵称初始化草稿，并清空上次错误提示。
 */
function openProfileSheet() {
  nicknameDraft.value = me.value?.nickname || ''
  profileError.value = ''
  openSheet('profile')
}

/**
 * 选择头像文件（相册或相机）。
 * 平台差异由 runtime 抹平：小程序返回临时路径，H5 返回 File 对象。
 * @returns 选中的文件引用；用户取消时返回 null
 * @throws Error 选择失败（如权限拒绝）时抛出
 */
function chooseAvatarFile(): Promise<string | Blob | null> {
  return new Promise((resolve, reject) => {
    runtime.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      sizeType: ['compressed'],
      success: (result: any) => {
        const picked = result?.tempFiles?.[0]?.tempFilePath
        if (picked) resolve(picked)
        else reject(new Error(avatarPickFailedCopy))
      },
      fail: (error: any) => {
        const message = String(error?.errMsg || '')
        if (message.includes('cancel')) resolve(null)
        else reject(new Error(avatarPickFailedCopy))
      }
    })
  })
}

/**
 * 更换账号头像：上传成功即保存生效，并同步更新「我的」页头像。
 */
async function pickAvatar() {
  if (avatarBusy.value) return
  avatarBusy.value = true
  profileError.value = ''
  try {
    const file = await chooseAvatarFile()
    if (!file) return
    const result = await api.uploadMeAvatar(file)
    if (me.value) me.value.avatar_url = result.avatar_url
    uni.showToast({ title: avatarUpdatedCopy, icon: 'none' })
  } catch (error: any) {
    const title = error?.message === avatarPickFailedCopy
      ? avatarPickFailedCopy
      : userFacingMessage(error, avatarUploadFailedCopy)
    uni.showToast({ title, icon: 'none' })
  } finally {
    avatarBusy.value = false
  }
}

/**
 * 移除账号头像：成功后回退为默认头像占位。
 */
async function removeAvatar() {
  if (avatarBusy.value) return
  avatarBusy.value = true
  try {
    await api.removeMeAvatar()
    if (me.value) me.value.avatar_url = null
    uni.showToast({ title: avatarRemovedCopy, icon: 'none' })
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, avatarRemoveFailedCopy), icon: 'none' })
  } finally {
    avatarBusy.value = false
  }
}

/**
 * 保存昵称：前端先做去空白与长度校验，服务端成功后再回写 me 并关闭面板。
 */
async function saveProfile() {
  const nickname = nicknameDraft.value.trim()
  if (!nickname) {
    profileError.value = nicknameEmptyCopy
    return
  }
  if (profileBusy.value) return
  profileBusy.value = true
  profileError.value = ''
  try {
    const result = await api.updateMeProfile({ nickname })
    if (me.value) me.value.nickname = result.nickname
    closeSheet()
    uni.showToast({ title: profileSavedCopy, icon: 'none' })
  } catch (error: any) {
    profileError.value = userFacingMessage(error, profileSaveFailedCopy)
  } finally {
    profileBusy.value = false
  }
}

/**
 * 账号管理确认：退出登录保留设备身份；切换账号额外清除设备身份。
 * 确认后立即清理本机会话并回首页登录态，服务端数据不动。
 * @param switchAccount true 表示切换账号，false 表示退出登录
 */
async function askSignOut(switchAccount: boolean) {
  const result = await openDialog({
    title: switchAccount ? switchConfirmTitle : logoutConfirmTitle,
    message: switchAccount ? switchConfirmCopy.value : logoutConfirmCopy,
    confirmText: switchAccount ? '确认切换' : '确认退出',
    danger: switchAccount
  })
  if (!result.confirm) return
  signOut({ switchAccount })
  closeSheet()
  uni.reLaunch({ url: '/pages/index/index' })
}

function openSheet(kind: SheetKind) {
  sheet.kind = kind
  sheet.visible = true
  if (kind === 'rights') {
    void loadRights()
  }
  if (kind === 'account') {
    void refreshConsents()
  }
}

// 跳转参数落地：仅在数据就绪后消费一次，避免重复弹层
function applyPendingSection() {
  const section = pendingSection.value
  if (!section) return
  pendingSection.value = ''
  openSheet(section === 'consents' ? 'account' : 'rights')
}
function closeSheet() {
  sheet.visible = false
  feedbackBusy.value = false
  profileError.value = ''
}
function openDoc(key: DocKey) {
  docKey.value = key
  openSheet('doc')
}
function openOverview() {
  openSheet('overview')
}

async function loadRights() {
  if (rightsLoading.value) return
  rightsLoading.value = true
  rightsError.value = ''
  try {
    const result = await api.rightsRequests()
    rightsItems.value = result.requests || []
  } catch (error: any) {
    rightsError.value = userFacingMessage(error, '申请记录读取失败，请稍后重试。')
  } finally {
    rightsLoading.value = false
  }
}

async function submitRights(type: 'access' | 'correct' | 'export' | 'withdraw' | 'delete' | 'deactivate') {
  if (rightsBusy.value) return
  rightsBusy.value = true
  try {
    const result = await api.rightsRequest(type)
    const due = result.sla_due_at ? String(result.sla_due_at).slice(0, 10) : ''
    void openDialog({
      title: '已提交受理',
      message: `受理编号 ${result.request_no}${due ? `，预计 ${due} 前答复` : ''}。进度可在申请记录中查看。`,
      showCancel: false,
      confirmText: '知道了'
    })
    void loadRights()
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, '提交失败，请稍后重试。'), icon: 'none' })
  } finally {
    rightsBusy.value = false
  }
}

async function requestCorrect() {
  const result = await openDialog({
    title: '更正信息',
    message: '档案信息可在「档案」页自助修改；问答、报告与日志类信息可提交更正申请。',
    confirmText: '提交申请'
  })
  if (result.confirm) void submitRights('correct')
}
async function requestExport() {
  const result = await openDialog({
    title: '复制与导出',
    message: '导出内容包含档案、问答与报告等个人信息；生成后可在本页下载，链接 24 小时内有效、仅可下载一次。',
    confirmText: '提交导出'
  })
  if (result.confirm) void submitRights('export')
}
async function requestDelete() {
  const result = await openDialog({
    title: '删除个人信息',
    message: '将提交整账户数据删除申请：删除后不可恢复；订单与交易记录按法定义务留存。单条档案可在「档案」页直接删除。',
    confirmText: '提交申请',
    danger: true
  })
  if (result.confirm) void submitRights('delete')
}
async function deactivateFlow() {
  const result = await openDialog({
    title: '账号注销',
    message: '注销后数据删除、不可恢复；订单与交易记录按法定义务留存。确认提交注销申请吗？',
    confirmText: '提交注销',
    danger: true
  })
  if (result.confirm) void submitRights('deactivate')
}

async function withdrawFlow() {
  const options: { label: string; type: string }[] = []
  if (consentBase.value) options.push({ label: '撤回基础同意', type: baseConsentType })
  if (consentChild.value) options.push({ label: '撤回儿童信息单独同意', type: childConsentType })
  if (!options.length) {
    uni.showToast({ title: '当前没有可撤回的同意项', icon: 'none' })
    return
  }
  if (options.length === 1) {
    askWithdraw(options[0].type)
    return
  }
  const picked = await openActionSheet(options.map((option) => option.label))
  if (picked !== null && options[picked]) askWithdraw(options[picked].type)
}
async function askWithdraw(type: string) {
  const isBase = type === baseConsentType
  const result = await openDialog({
    title: isBase ? '撤回基础同意' : '撤回儿童信息单独同意',
    message: isBase ? withdrawBaseNote : withdrawChildNote,
    confirmText: '确认撤回',
    danger: true
  })
  if (result.confirm) void doWithdraw(type)
}
async function doWithdraw(type: string) {
  if (withdrawBusy.value) return
  withdrawBusy.value = true
  try {
    await api.withdrawConsent(type)
    await refreshConsents()
    uni.showToast({ title: '已撤回同意', icon: 'none' })
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, '撤回失败，请稍后重试。'), icon: 'none' })
  } finally {
    withdrawBusy.value = false
  }
}

function readTempText(path: string) {
  try {
    const manager = (uni as unknown as {
      getFileSystemManager?: () => { readFileSync: (filePath: string, encoding: string) => string }
    }).getFileSystemManager?.()
    if (!manager) return ''
    return String(manager.readFileSync(path, 'utf-8') || '')
  } catch {
    return ''
  }
}
function downloadExport(requestNo: string) {
  const token = uni.getStorageSync(TOKEN_KEY)
  uni.downloadFile({
    url: api.rightsDownloadUrl(requestNo),
    header: typeof token === 'string' && token ? { Authorization: `Bearer ${token}` } : {},
    success: (res) => {
      const text = readTempText(res.tempFilePath)
      if (res.statusCode === 200 && text) {
        uni.setClipboardData({
          data: text,
          success: () => uni.showToast({ title: '导出内容已复制，可粘贴保存', icon: 'none' })
        })
        return
      }
      let message = '下载失败，请稍后重试'
      try {
        const parsed = JSON.parse(text)
        if (parsed && typeof parsed.message === 'string' && parsed.message) message = parsed.message
      } catch {
        // 保持默认提示
      }
      uni.showToast({ title: message, icon: 'none' })
    },
    fail: () => {
      uni.showToast({ title: '下载失败，请检查网络后重试', icon: 'none' })
    }
  })
}

async function submitFeedback() {
  const content = feedbackText.value.trim()
  if (!content || feedbackBusy.value) return
  feedbackBusy.value = true
  try {
    const result = await api.feedback(content)
    feedbackText.value = ''
    closeSheet()
    void openDialog({
      title: '已收到你的反馈',
      message: `受理编号 ${result.feedback_no}，预计 ${result.receipt_hours} 小时内处理。`,
      showCancel: false,
      confirmText: '知道了'
    })
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, '提交失败，请稍后重试。'), icon: 'none' })
  } finally {
    feedbackBusy.value = false
  }
}

onLoad((query) => {
  const section = decodeRouteValue(query?.section)
  if (section === 'rights' || section === 'consents') pendingSection.value = section
})
onShow(() => { void load() })
onPullDownRefresh(() => { void load() })
</script>

<style scoped>
.me-page { min-height: 100vh; padding-bottom: calc(272rpx + env(safe-area-inset-bottom)); background-color: var(--bg); }
.page-body { padding: 24rpx 32rpx 0; }
.pressed { opacity: .82; }

.user-card { display: flex; align-items: center; gap: 22rpx; padding: 30rpx 28rpx; background: var(--surface); border: 1px solid var(--line-warm); border-radius: var(--r-card) var(--r-card) 0 0; box-shadow: var(--shadow-card); }
.user-avatar { position: relative; width: 96rpx; height: 96rpx; flex: none; overflow: hidden; border-radius: 50%; background: var(--primary-soft); border: 1px solid var(--line-warm); }
.user-avatar-img { display: block; width: 100%; height: 100%; border-radius: 50%; }
.glyph { position: absolute; top: 0; right: 0; bottom: 0; left: 0; }
.glyph-person-lg::before { position: absolute; top: 22rpx; left: 35rpx; width: 20rpx; height: 20rpx; border: 4rpx solid var(--primary); border-radius: 50%; content: ''; }
.glyph-person-lg::after { position: absolute; top: 52rpx; left: 23rpx; width: 42rpx; height: 19rpx; border: 4rpx solid var(--primary); border-bottom: 0; border-radius: 22rpx 22rpx 0 0; content: ''; }
.user-main { display: flex; flex: 1; flex-direction: column; min-width: 0; gap: 8rpx; }
.user-name-row { display: flex; align-items: center; gap: 16rpx; }
.user-name { color: var(--ink-1); font-size: 33rpx; font-weight: 650; }
.edit-pill { flex: none; margin: 0; padding: 6rpx 22rpx; color: var(--primary-press); background: transparent; border: 1rpx solid var(--primary); border-radius: var(--r-control); font-size: 22rpx; line-height: 1.5; }
.user-uid { overflow: hidden; color: var(--ink-3); font-size: 23rpx; text-overflow: ellipsis; white-space: nowrap; }

.member-band { display: flex; align-items: center; justify-content: space-between; gap: 16rpx; padding: 20rpx 28rpx 22rpx; border-radius: 0 0 var(--r-card) var(--r-card); }
.member-band.tone-active { background-color: var(--primary-soft); }
.member-band.tone-free { background-color: var(--surface-warm); border: 1px solid var(--line-warm); border-top: 0; }
.member-band.tone-unknown { background-color: var(--warn-soft); }
.member-text { color: var(--ink-1); font-size: 26rpx; font-weight: 650; }
.member-band.tone-free .member-text { color: var(--ink-2); }
.member-pill { flex: none; padding: 8rpx 20rpx; color: var(--warn); border: 1rpx solid var(--warn); border-radius: var(--r-control); font-size: 22rpx; }

.group-title { display: block; margin: 34rpx 0 14rpx; color: var(--ink-3); font-size: 24rpx; }
.menu-card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-card); box-shadow: var(--shadow-card); overflow: hidden; }
.card-row { display: flex; align-items: center; gap: 20rpx; min-height: 118rpx; padding: 20rpx 26rpx; }
.card-row + .card-row { border-top: 1px solid var(--line); }
.row-pressed { background: var(--surface-warm); }
.row-icon { position: relative; width: 72rpx; height: 72rpx; flex: none; border-radius: 50%; }
.icon-info { background: var(--info-soft); }
.icon-warn { background: var(--warn-soft); }
.icon-primary { background: var(--primary-soft); }
.row-main { display: flex; flex: 1; flex-direction: column; min-width: 0; gap: 6rpx; }
.row-title { color: var(--ink-1); font-size: 28rpx; font-weight: 650; }
.row-value { flex: none; color: var(--ink-3); font-size: 24rpx; font-variant-numeric: tabular-nums; }
.row-arrow { flex: none; width: 12rpx; height: 12rpx; margin-left: 4rpx; border-top: 1rpx solid var(--ink-3); border-right: 1rpx solid var(--ink-3); transform: rotate(45deg); }
.term-links { flex-direction: row; flex-wrap: wrap; align-items: center; gap: 10rpx; min-height: 78rpx; }
.inline-link { color: var(--primary-press); font-size: 27rpx; }
.inline-dot { color: var(--ink-3); font-size: 24rpx; }

.glyph-child::before { position: absolute; top: 17rpx; left: 26rpx; width: 14rpx; height: 14rpx; border: 3rpx solid var(--info); border-radius: 50%; content: ''; }
.glyph-child::after { position: absolute; top: 38rpx; left: 17rpx; width: 32rpx; height: 15rpx; border: 3rpx solid var(--info); border-bottom: 0; border-radius: 17rpx 17rpx 0 0; content: ''; }
.glyph-pet::before { position: absolute; top: 34rpx; left: 22rpx; width: 28rpx; height: 22rpx; background: var(--warn); border-radius: 50% 50% 45% 45% / 60% 60% 40% 40%; content: ''; }
.glyph-pet::after { position: absolute; top: 18rpx; left: 20rpx; width: 13rpx; height: 13rpx; background: var(--warn); border-radius: 50%; box-shadow: 19rpx 2rpx 0 var(--warn); content: ''; }
.glyph-record::before { position: absolute; top: 22rpx; left: 18rpx; width: 36rpx; height: 3rpx; background: var(--primary); border-radius: 2rpx; box-shadow: 0 11rpx 0 var(--primary), 0 22rpx 0 var(--primary); content: ''; }
.glyph-feedback::before { position: absolute; top: 18rpx; left: 14rpx; width: 44rpx; height: 30rpx; border: 3rpx solid var(--primary); border-radius: 12rpx; content: ''; }
.glyph-feedback::after { position: absolute; top: 44rpx; left: 24rpx; width: 12rpx; height: 12rpx; border-left: 3rpx solid var(--primary); border-bottom: 3rpx solid var(--primary); transform: rotate(-45deg); content: ''; }
.glyph-member::before { position: absolute; top: 16rpx; left: 16rpx; width: 36rpx; height: 36rpx; border: 3rpx solid var(--warn); border-radius: 50%; content: ''; }
.glyph-member::after { position: absolute; top: 28rpx; left: 28rpx; width: 12rpx; height: 12rpx; background: var(--warn); border-radius: 50%; content: ''; }
.glyph-shield::before { position: absolute; top: 15rpx; left: 19rpx; width: 28rpx; height: 34rpx; border: 3rpx solid var(--info); border-radius: 12rpx 12rpx 16rpx 16rpx; content: ''; }
.glyph-shield::after { position: absolute; top: 26rpx; left: 28rpx; width: 12rpx; height: 7rpx; border-left: 3rpx solid var(--info); border-bottom: 3rpx solid var(--info); transform: rotate(-45deg); content: ''; }
.glyph-doc::before { position: absolute; top: 16rpx; left: 21rpx; width: 28rpx; height: 38rpx; border: 3rpx solid var(--info); border-radius: 5rpx; content: ''; }
.glyph-doc::after { position: absolute; top: 28rpx; left: 29rpx; width: 14rpx; height: 10rpx; border-top: 3rpx solid var(--info); border-bottom: 3rpx solid var(--info); content: ''; }
.glyph-link::before { position: absolute; top: 23rpx; left: 13rpx; width: 24rpx; height: 24rpx; border: 3rpx solid var(--info); border-radius: 50%; content: ''; }
.glyph-link::after { position: absolute; top: 23rpx; left: 34rpx; width: 24rpx; height: 24rpx; border: 3rpx solid var(--info); border-radius: 50%; content: ''; }
.glyph-terms::before { position: absolute; top: 16rpx; left: 21rpx; width: 28rpx; height: 38rpx; border: 3rpx solid var(--primary); border-radius: 5rpx; content: ''; }
.glyph-terms::after { position: absolute; top: 28rpx; left: 29rpx; width: 14rpx; height: 10rpx; border-top: 3rpx solid var(--primary); border-bottom: 3rpx solid var(--primary); content: ''; }
.glyph-ai::before { position: absolute; top: 20rpx; left: 20rpx; width: 26rpx; height: 26rpx; border: 3rpx solid var(--primary); border-radius: 50%; content: ''; }
.glyph-ai::after { position: absolute; top: 31rpx; left: 31rpx; width: 9rpx; height: 9rpx; background: var(--primary); border-radius: 50%; content: ''; }
.glyph-person::before { position: absolute; top: 17rpx; left: 26rpx; width: 14rpx; height: 14rpx; border: 3rpx solid var(--primary); border-radius: 50%; content: ''; }
.glyph-person::after { position: absolute; top: 38rpx; left: 17rpx; width: 32rpx; height: 15rpx; border: 3rpx solid var(--primary); border-bottom: 0; border-radius: 17rpx 17rpx 0 0; content: ''; }

.footer-note { display: block; padding: 44rpx 0 8rpx; color: var(--ink-3); font-size: 24rpx; text-align: center; }

.sheet-mask { position: fixed; top: 0; right: 0; bottom: 0; left: 0; z-index: 80; background: rgba(46, 51, 46, .4); }
.sheet { position: fixed; right: 0; bottom: 0; left: 0; z-index: 90; display: flex; flex-direction: column; max-height: 88vh; padding-bottom: env(safe-area-inset-bottom); background: var(--surface); border-radius: var(--r-card) var(--r-card) 0 0; }
.sheet-head { display: flex; align-items: center; justify-content: space-between; padding: 28rpx 28rpx 16rpx; }
.sheet-title { color: var(--ink-1); font-size: 31rpx; font-weight: 650; }
.sheet-close { margin: 0; padding: 4rpx 0; color: var(--ink-3); background: transparent; border: 0; font-size: 25rpx; line-height: 1.4; }
.sheet-scroll { height: 64vh; padding: 0 28rpx; box-sizing: border-box; }
.sheet-caption { display: block; margin: 6rpx 0 4rpx; color: var(--ink-3); font-size: 23rpx; line-height: 1.6; }
.sheet-section { display: block; margin-top: 34rpx; color: var(--ink-1); font-size: 28rpx; font-weight: 650; }
.sheet-note { display: block; margin: 18rpx 0 8rpx; color: var(--ink-3); font-size: 22rpx; line-height: 1.6; }
.sheet-gap { height: 34rpx; }

.sheet-list { margin-top: 18rpx; background: var(--surface-warm); border: 1px solid var(--line); border-radius: var(--r-inner); overflow: hidden; }
.list-row { display: flex; align-items: center; gap: 18rpx; min-height: 96rpx; padding: 18rpx 22rpx; }
.list-row + .list-row { border-top: 1px solid var(--line); }
.list-main { display: flex; flex: 1; flex-direction: column; min-width: 0; gap: 6rpx; }
.list-title { color: var(--ink-1); font-size: 26rpx; font-weight: 650; }
.list-sub { color: var(--ink-3); font-size: 22rpx; line-height: 1.55; }
.list-value { flex: none; color: var(--ink-2); font-size: 24rpx; font-variant-numeric: tabular-nums; }
.list-note { display: flex; align-items: center; justify-content: space-between; gap: 16rpx; margin-top: 18rpx; padding: 22rpx; background: var(--surface-warm); border: 1px solid var(--line); border-radius: var(--r-inner); }
.note-error { color: var(--danger); font-size: 23rpx; line-height: 1.5; }

.action-pill { flex: none; display: inline-flex; align-items: center; justify-content: center; min-height: 62rpx; margin: 0; padding: 0 26rpx; color: var(--primary-press); background: transparent; border: 1rpx solid var(--primary); border-radius: var(--r-control); font-size: 23rpx; line-height: 1; }
.action-pill.disabled { opacity: .55; }
.danger-pill { color: var(--danger); border-color: var(--danger); }
.mini-link { align-self: flex-start; margin: 0; padding: 6rpx 0; color: var(--primary-press); background: transparent; border: 0; font-size: 24rpx; line-height: 1.4; }

.request-row { display: flex; flex-direction: column; gap: 8rpx; padding: 20rpx 22rpx; }
.request-row + .request-row { border-top: 1px solid var(--line); }
.request-head { display: flex; align-items: center; justify-content: space-between; gap: 14rpx; }
.request-status { flex: none; padding: 4rpx 16rpx; border-radius: var(--r-control); font-size: 20rpx; line-height: 1.5; }
.tone-wait { color: var(--info); background: var(--info-soft); }
.tone-ok { color: var(--primary-press); background: var(--primary-soft); }
.tone-done { color: var(--ink-2); background: var(--surface); border: 1px solid var(--line); }
.tone-reject { color: var(--danger); background: var(--danger-soft); }
.request-reject { color: var(--danger); font-size: 22rpx; line-height: 1.55; }
.request-no { color: var(--ink-3); font-size: 21rpx; }

.doc-para { display: block; margin-top: 20rpx; color: var(--ink-2); font-size: 26rpx; line-height: 1.75; }

.feedback-input { width: 100%; min-height: 220rpx; margin-top: 20rpx; padding: 22rpx; box-sizing: border-box; color: var(--ink-1); background: var(--surface-warm); border: 1px solid var(--line); border-radius: var(--r-inner); font-size: 27rpx; line-height: 1.65; }
.field-placeholder { color: var(--ink-3); }
.sheet-actions { display: flex; gap: 18rpx; padding: 20rpx 28rpx 26rpx; border-top: 1px solid var(--line); }
.primary-button { display: flex; flex: 1; align-items: center; justify-content: center; min-height: 88rpx; margin: 0; color: var(--on-primary); background: var(--primary); border: 0; border-radius: var(--r-control); font-size: 28rpx; font-weight: 650; }
.primary-button.disabled { opacity: .55; }
.ghost-button { flex: none; display: flex; align-items: center; justify-content: center; width: 180rpx; min-height: 88rpx; margin: 0; color: var(--ink-2); background: transparent; border: 1px solid var(--line); border-radius: var(--r-control); font-size: 26rpx; }
.danger-button { display: flex; align-items: center; justify-content: center; min-height: 88rpx; margin: 22rpx 0 0; color: var(--danger); background: var(--danger-soft); border: 1rpx solid var(--danger); border-radius: var(--r-control); font-size: 27rpx; font-weight: 650; }
.danger-button.disabled { opacity: .55; }

.profile-head { display: flex; align-items: center; gap: 20rpx; margin-top: 22rpx; padding: 22rpx; background: var(--surface-warm); border: 1px solid var(--line); border-radius: var(--r-inner); }
.profile-avatar { position: relative; width: 96rpx; height: 96rpx; flex: none; overflow: hidden; background: var(--primary-soft); border: 1px solid var(--line-warm); border-radius: 50%; }
.profile-avatar-img { display: block; width: 100%; height: 100%; border-radius: 50%; }
.profile-head-main { display: flex; flex: 1; flex-direction: column; min-width: 0; gap: 6rpx; }
.profile-action { flex: none; color: var(--primary-press); font-size: 24rpx; font-weight: 650; }
.profile-input { width: 100%; min-height: 88rpx; margin-top: 16rpx; padding: 0 22rpx; box-sizing: border-box; color: var(--ink-1); background: var(--surface-warm); border: 1px solid var(--line); border-radius: var(--r-inner); font-size: 27rpx; }
.profile-error { display: block; margin-top: 14rpx; color: var(--danger); font-size: 23rpx; line-height: 1.5; }
</style>
