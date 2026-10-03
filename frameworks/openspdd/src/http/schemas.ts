const nameSchema = { type: 'string', minLength: 1, maxLength: 100, pattern: '\\S' } as const;

export const createGroupBody = {
  type: 'object',
  additionalProperties: false,
  required: ['name'],
  properties: { name: nameSchema },
} as const;

export const addMemberBody = createGroupBody;

export const recordExpenseBody = {
  type: 'object',
  additionalProperties: false,
  required: ['payerId', 'amount', 'description', 'participantIds'],
  properties: {
    payerId: { type: 'string', minLength: 1 },
    amount: { type: 'string', pattern: '^\\d{1,10}(\\.\\d{1,2})?$' },
    description: { type: 'string', minLength: 1, maxLength: 200, pattern: '\\S' },
    participantIds: {
      type: 'array',
      minItems: 1,
      maxItems: 100,
      items: { type: 'string', minLength: 1 },
    },
  },
} as const;

export const groupIdParams = {
  type: 'object',
  required: ['groupId'],
  properties: { groupId: { type: 'string' } },
} as const;

export interface GroupIdParams {
  groupId: string;
}

export interface NameBody {
  name: string;
}

export interface RecordExpenseBody {
  payerId: string;
  amount: string;
  description: string;
  participantIds: string[];
}
