import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/api/client";
import { useAuth } from "@/stores/auth";
import { LoginForm, RegisterForm } from "./LoginPage";

function renderIn(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

afterEach(() => {
  vi.restoreAllMocks();
  useAuth.getState().clear();
});

describe("LoginForm validation", () => {
  it("shows inline errors under empty fields and does not call the API", async () => {
    const post = vi.spyOn(api, "post");
    const user = userEvent.setup();
    renderIn(<LoginForm />);
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Enter your email")).toBeInTheDocument();
    expect(screen.getByText("Enter your password")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
    expect(post).not.toHaveBeenCalled();
  });

  it("rejects a malformed email", async () => {
    const user = userEvent.setup();
    renderIn(<LoginForm />);
    await user.type(screen.getByLabelText("Email"), "not-an-email");
    await user.type(screen.getByLabelText("Password"), "whatever1");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Enter a valid email address")).toBeInTheDocument();
  });

  it("shows the API error in a banner", async () => {
    vi.spyOn(api, "post").mockRejectedValue(
      Object.assign(new Error("401"), {
        isAxiosError: true,
        response: { status: 401, data: { detail: "Incorrect email or password" } },
      }),
    );
    const user = userEvent.setup();
    renderIn(<LoginForm />);
    await user.type(screen.getByLabelText("Email"), "rahul@example.com");
    await user.type(screen.getByLabelText("Password"), "wrong-pass1");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password");
  });

  it("stores the session on success", async () => {
    const user = userEvent.setup();
    const post = vi.spyOn(api, "post").mockResolvedValue({
      data: {
        access_token: "tok",
        token_type: "bearer",
        expires_in: 900,
        user: {
          id: 1,
          email: "rahul@example.com",
          full_name: "Rahul",
          role: "seeker",
          is_active: true,
          created_at: "",
          company: null,
        },
      },
    });
    renderIn(<LoginForm />);
    await user.click(screen.getAllByRole("button", { name: "Fill" })[0]);
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(useAuth.getState().status).toBe("authenticated"));
    expect(post).toHaveBeenCalledWith("/api/auth/login", {
      email: "rahul@example.com",
      password: "Seeker@123",
    });
    expect(useAuth.getState().accessToken).toBe("tok");
  });
});

describe("RegisterForm validation", () => {
  it("enforces password rules and requires a company for recruiters", async () => {
    const user = userEvent.setup();
    renderIn(<RegisterForm />);
    await user.type(screen.getByLabelText("Full name"), "Asha Rao");
    await user.type(screen.getByLabelText("Work email"), "asha@example.com");
    await user.type(screen.getByLabelText("Password"), "short");
    await user.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Use at least 8 characters")).toBeInTheDocument();

    await user.clear(screen.getByLabelText("Password"));
    await user.type(screen.getByLabelText("Password"), "onlyletters");
    await user.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Include at least one number")).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: /recruiter/i }));
    await user.clear(screen.getByLabelText("Password"));
    await user.type(screen.getByLabelText("Password"), "Secret123");
    await user.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Enter the company you are hiring for")).toBeInTheDocument();
  });
});
