import { randomUUID } from 'node:crypto';
import type { Group, Member } from '../domain/types.js';
import { ConflictError, NotFoundError } from '../errors.js';
import type { GroupRepository, MemberRepository } from '../repositories/types.js';

export class GroupService {
  constructor(
    private readonly groups: GroupRepository,
    private readonly members: MemberRepository,
  ) {}

  createGroup(name: string): Group {
    const group: Group = {
      id: randomUUID(),
      name: name.trim(),
      createdAt: new Date().toISOString(),
    };
    this.groups.save(group);
    return group;
  }

  getGroup(groupId: string): Group {
    const group = this.groups.findById(groupId);
    if (group === undefined) {
      throw new NotFoundError('GROUP_NOT_FOUND', 'Group not found', { groupId });
    }
    return group;
  }

  addMember(groupId: string, name: string): Member {
    this.getGroup(groupId);
    const trimmed = name.trim();
    const normalized = trimmed.toLocaleLowerCase('en');
    const exists = this.members
      .findByGroup(groupId)
      .some((m) => m.name.toLocaleLowerCase('en') === normalized);
    if (exists) {
      throw new ConflictError('A member with this name already exists in the group', {
        name: trimmed,
      });
    }
    const member: Member = {
      id: randomUUID(),
      groupId,
      name: trimmed,
      seq: this.members.countByGroup(groupId),
    };
    this.members.save(member);
    return member;
  }

  listMembers(groupId: string): Member[] {
    this.getGroup(groupId);
    return this.members.findByGroup(groupId);
  }
}
