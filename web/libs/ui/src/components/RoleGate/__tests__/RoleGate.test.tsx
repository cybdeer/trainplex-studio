import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { RoleGate } from "../RoleGate";

describe("RoleGate", () => {
  it("renders children when user role is in allow list (admin)", () => {
    render(
      <RoleGate allow={["admin"]} userRole="admin">
        <span data-testid="gated">visible</span>
      </RoleGate>,
    );
    expect(screen.getByTestId("gated")).toBeInTheDocument();
    expect(screen.getByTestId("gated")).toHaveTextContent("visible");
  });

  it("blocks trainer when only admin is allowed; renders default null fallback", () => {
    const { container } = render(
      <RoleGate allow={["admin"]} userRole="trainer">
        <span data-testid="gated">visible</span>
      </RoleGate>,
    );
    expect(screen.queryByTestId("gated")).not.toBeInTheDocument();
    // default fallback is null → fragment renders nothing
    expect(container).toBeEmptyDOMElement();
  });

  it("renders supplied fallback when blocked", () => {
    render(
      <RoleGate
        allow={["admin"]}
        userRole="reviewer"
        fallback={<span data-testid="fallback">no access</span>}
      >
        <span data-testid="gated">visible</span>
      </RoleGate>,
    );
    expect(screen.queryByTestId("gated")).not.toBeInTheDocument();
    expect(screen.getByTestId("fallback")).toHaveTextContent("no access");
  });

  it("blocks when userRole is undefined", () => {
    const { container } = render(
      <RoleGate allow={["admin", "qa_lead"]} userRole={undefined}>
        <span data-testid="gated">visible</span>
      </RoleGate>,
    );
    expect(screen.queryByTestId("gated")).not.toBeInTheDocument();
    expect(container).toBeEmptyDOMElement();
  });

  it("blocks when userRole is null", () => {
    render(
      <RoleGate
        allow={["admin"]}
        userRole={null}
        fallback={<span data-testid="fallback">denied</span>}
      >
        <span data-testid="gated">visible</span>
      </RoleGate>,
    );
    expect(screen.queryByTestId("gated")).not.toBeInTheDocument();
    expect(screen.getByTestId("fallback")).toBeInTheDocument();
  });

  it("blocks when userRole is empty string", () => {
    const { container } = render(
      <RoleGate allow={["admin"]} userRole="">
        <span data-testid="gated">visible</span>
      </RoleGate>,
    );
    expect(screen.queryByTestId("gated")).not.toBeInTheDocument();
    expect(container).toBeEmptyDOMElement();
  });

  it("supports multi-role allow lists (qa_lead allowed)", () => {
    render(
      <RoleGate allow={["admin", "qa_lead"]} userRole="qa_lead">
        <span data-testid="gated">visible</span>
      </RoleGate>,
    );
    expect(screen.getByTestId("gated")).toBeInTheDocument();
  });

  it("supports multi-role allow lists (reviewer not in list)", () => {
    render(
      <RoleGate
        allow={["admin", "qa_lead"]}
        userRole="reviewer"
        fallback={<span data-testid="fallback">denied</span>}
      >
        <span data-testid="gated">visible</span>
      </RoleGate>,
    );
    expect(screen.queryByTestId("gated")).not.toBeInTheDocument();
    expect(screen.getByTestId("fallback")).toBeInTheDocument();
  });

  it("blocks unknown role strings", () => {
    const { container } = render(
      <RoleGate allow={["admin"]} userRole="superuser">
        <span data-testid="gated">visible</span>
      </RoleGate>,
    );
    expect(screen.queryByTestId("gated")).not.toBeInTheDocument();
    expect(container).toBeEmptyDOMElement();
  });
});
