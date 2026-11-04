import { Button, Form, Select, Space } from "antd";
import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";
import type { Member } from "../types";
import { roleAllowsEvent } from "../eventKinds";
export type RoleOption = { id: number; name: string };
export default function EventTeamFields({
  roles,
  members,
}: {
  roles: RoleOption[];
  members: Member[];
}) {
  const form = Form.useFormInstance();
  return (
    <Form.List name="role_slots">
      {(fields, { add, remove }) => (
        <>
          <p className="subtle">
            Выберите нужные роли и служителей. Места можно оставить свободными и
            заполнить позже.
          </p>
          {fields.map((field) => (
            <div className="event-team-row" key={field.key}>
              <Form.Item
                name={[field.name, "ministry_role_id"]}
                rules={[{ required: true, message: "Выберите роль" }]}
              >
                <Select
                  aria-label={`Роль ${field.name + 1}`}
                  placeholder="Роль"
                  options={roles.map((role) => ({
                    value: role.id,
                    label: role.name,
                  }))}
                  onChange={() =>
                    form.setFieldValue(
                      ["role_slots", field.name, "user_ministry_role_id"],
                      null,
                    )
                  }
                />
              </Form.Item>
              <Form.Item noStyle shouldUpdate>
                {() => {
                  const roleId = form.getFieldValue([
                    "role_slots",
                    field.name,
                    "ministry_role_id",
                  ]);
                  return (
                    <Form.Item name={[field.name, "user_ministry_role_id"]}>
                      <Select
                        aria-label={`Служитель ${field.name + 1}`}
                        placeholder="Пока не назначен"
                        allowClear
                        options={members.flatMap((member) =>
                          member.roles
                            .filter(
                              (role) =>
                                role.id === roleId &&
                                (!form.getFieldValue("event_kind") ||
                                  roleAllowsEvent(
                                    role,
                                    form.getFieldValue("event_kind"),
                                  )),
                            )
                            .map((role) => ({
                              value: role.user_ministry_role_id,
                              label: `${member.name} ${member.surname}`,
                            })),
                        )}
                      />
                    </Form.Item>
                  );
                }}
              </Form.Item>
              <Button
                type="text"
                aria-label={`Убрать место ${field.name + 1}`}
                icon={<MinusCircleOutlined />}
                onClick={() => remove(field.name)}
              />
            </div>
          ))}
          <Space>
            <Button
              type="dashed"
              icon={<PlusOutlined />}
              onClick={() => add({ user_ministry_role_id: null })}
            >
              Добавить место в команде
            </Button>
          </Space>
        </>
      )}
    </Form.List>
  );
}
