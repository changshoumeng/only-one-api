import {
  Activity,
  History,
  KeyRound,
  ServerCog,
  type LucideIcon,
} from '@lucide/vue';

export interface NavigationItem {
  routeName: string;
  label: string;
  description: string;
  icon: LucideIcon;
}

export const primaryNavigation: NavigationItem[] = [
  {
    routeName: 'usage',
    label: '使用量',
    description: '请求、Token 与费用概览',
    icon: Activity,
  },
  {
    routeName: 'api-manage',
    label: '接口管理',
    description: '供应商与模型配置',
    icon: ServerCog,
  },
  {
    routeName: 'key-manage',
    label: 'Key 管理',
    description: '访问密钥与启停状态',
    icon: KeyRound,
  },
  {
    routeName: 'chat-history',
    label: '对话历史',
    description: '请求记录与消息详情',
    icon: History,
  },
];
