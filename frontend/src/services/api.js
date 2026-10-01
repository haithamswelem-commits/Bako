const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "/api"
).replace(/\/+$/, "");

// =========================
// TOKEN HELPERS
// =========================

export const saveToken = (token) => {
  sessionStorage.setItem("token", token);
};

export const getToken = () => {
  return sessionStorage.getItem("token");
};

export const logout = () => {
  sessionStorage.removeItem("token");
  sessionStorage.removeItem("cycle_id");
};

// =========================
// CYCLE HELPERS
// =========================

export const saveCycleId = (cycleId) => {
  if (!cycleId) {
    sessionStorage.removeItem("cycle_id");
    return;
  }

  sessionStorage.setItem("cycle_id", cycleId);
};

export const getCycleId = () => {
  return sessionStorage.getItem("cycle_id");
};

// =========================
// AUTH HEADER
// =========================

const getAuthHeaders = () => {
  const token = getToken();

  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`
  };
};

const parseJsonResponse = async (res) => {
  const rawBody = await res.text();
  let data = {};

  if (rawBody) {
    try {
      data = JSON.parse(rawBody);
    } catch {
      if (!res.ok) {
        throw new Error(
          res.status >= 500
            ? "The service is temporarily unavailable. Please try again."
            : rawBody
        );
      }
      throw new Error("The server returned an unreadable response.");
    }
  }

  if (!res.ok) {
    throw new Error(
      data.detail ||
      data.error ||
      "Request failed"
    );
  }

  return data;
};

// =========================
// AUTH API
// =========================

export const registerUser = async (userData) => {
  const res = await fetch(`${API_BASE_URL}/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(userData)
  });

  return res.json();
};

export const loginUser = async (userData) => {
  const res = await fetch(`${API_BASE_URL}/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(userData)
  });

  return res.json();
};

export const getCurrentUser = async () => {
  const res = await fetch(`${API_BASE_URL}/me`, {
    headers: getAuthHeaders()
  });

  return res.json();
};

// =========================
// CYCLES
// =========================

export const createCycle = async (cycleData) => {
  const res = await fetch(`${API_BASE_URL}/cycle`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(cycleData)
  });

  return parseJsonResponse(res);
};

export const getCurrentCycle = async () => {
  const res = await fetch(
    `${API_BASE_URL}/current-cycle`,
    {
      headers: getAuthHeaders()
    }
  );

  return res.json();
};

// =========================
// CATEGORIES
// =========================

export const getCategories = async () => {
  const res = await fetch(`${API_BASE_URL}/categories`, {
    headers: getAuthHeaders()
  });
  return parseJsonResponse(res);
};

export const updateCurrentUser = async (profile) => {
  const res = await fetch(`${API_BASE_URL}/me`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(profile)
  });

  return parseJsonResponse(res);
};

export const getSubcategories = async (categoryId) => {
  const res = await fetch(
    `${API_BASE_URL}/subcategories?category_id=${categoryId}`,
    {
      headers: getAuthHeaders()
    }
  );

  return parseJsonResponse(res);
};

export const createCategory = async (name) => {
  const res = await fetch(`${API_BASE_URL}/categories`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ name })
  });
  return parseJsonResponse(res);
};

export const createSubcategory = async (categoryId, name) => {
  const res = await fetch(
    `${API_BASE_URL}/categories/${categoryId}/subcategories`,
    {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ name })
    }
  );
  return parseJsonResponse(res);
};

export const createCategoryPair = async (categoryName, subcategoryName) => {
  const res = await fetch(`${API_BASE_URL}/category-pairs`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({
      category_name: categoryName,
      subcategory_name: subcategoryName
    })
  });
  return parseJsonResponse(res);
};

export const updateCategory = async (categoryId, name) => {
  const res = await fetch(`${API_BASE_URL}/categories/${categoryId}`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify({ name })
  });
  return parseJsonResponse(res);
};

export const archiveCategory = async (categoryId) => {
  const res = await fetch(`${API_BASE_URL}/categories/${categoryId}`, {
    method: "DELETE",
    headers: getAuthHeaders()
  });
  return parseJsonResponse(res);
};

export const updateSubcategory = async (subcategoryId, name) => {
  const res = await fetch(`${API_BASE_URL}/subcategories/${subcategoryId}`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify({ name })
  });
  return parseJsonResponse(res);
};

export const archiveSubcategory = async (subcategoryId) => {
  const res = await fetch(`${API_BASE_URL}/subcategories/${subcategoryId}`, {
    method: "DELETE",
    headers: getAuthHeaders()
  });
  return parseJsonResponse(res);
};

export const suggestExpenseCategory = async (description) => {
  const res = await fetch(`${API_BASE_URL}/expense-category-suggestion`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ description })
  });
  return parseJsonResponse(res);
};

// =========================
// SUMMARY
// =========================

export const getSummary = async (cycleId) => {
  const res = await fetch(
    `${API_BASE_URL}/daily-summary?cycle_id=${cycleId}`,
    {
      headers: getAuthHeaders()
    }
  );

  return res.json();
};

// =========================
// ANALYSIS
// =========================

export const getAnalysis = async (cycleId) => {
  const res = await fetch(
    `${API_BASE_URL}/spending-analysis?cycle_id=${cycleId}`,
    {
      headers: getAuthHeaders()
    }
  );

  return res.json();
};

export const getAIInsights = async (cycleId) => {
  const res = await fetch(
    `${API_BASE_URL}/ai-insights?cycle_id=${cycleId}`,
    {
      headers: getAuthHeaders()
    }
  );

  return res.json();
};

export const getCycles = async () => {
  const res = await fetch(`${API_BASE_URL}/cycles`, {
    headers: getAuthHeaders()
  });

  return parseJsonResponse(res);
};

export const getCycleSummary = async (cycleId) => {
  const res = await fetch(`${API_BASE_URL}/cycles/${cycleId}/summary`, {
    headers: getAuthHeaders()
  });

  return parseJsonResponse(res);
};

export const getCycleComparison = async (
  baseCycleId,
  comparisonCycleId
) => {
  const params = new URLSearchParams({
    base_cycle_id: String(baseCycleId),
    comparison_cycle_id: String(comparisonCycleId)
  });
  const res = await fetch(`${API_BASE_URL}/cycles/compare?${params}`, {
    headers: getAuthHeaders()
  });

  return parseJsonResponse(res);
};

export const updateCycle = async (cycleId, cycleData) => {
  const res = await fetch(`${API_BASE_URL}/cycles/${cycleId}`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(cycleData)
  });

  return parseJsonResponse(res);
};

export const deleteCycle = async (cycleId) => {
  const res = await fetch(`${API_BASE_URL}/cycles/${cycleId}`, {
    method: "DELETE",
    headers: getAuthHeaders()
  });

  return parseJsonResponse(res);
};

// =========================
// GOALS
// =========================

export const getGoals = async (activeOnly = false, cycleId = null) => {
  const params = new URLSearchParams({
    active_only: String(activeOnly)
  });

  if (cycleId) {
    params.set("cycle_id", String(cycleId));
  }

  const res = await fetch(`${API_BASE_URL}/goals?${params}`, {
    headers: getAuthHeaders()
  });

  return parseJsonResponse(res);
};

export const addCycleBudget = async (cycleId, amount, note = null) => {
  const res = await fetch(
    `${API_BASE_URL}/cycles/${cycleId}/budget-adjustments`,
    {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ amount: Number(amount), note })
    }
  );
  return parseJsonResponse(res);
};

export const createGoal = async (goalData) => {
  const res = await fetch(`${API_BASE_URL}/goals`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(goalData)
  });

  return parseJsonResponse(res);
};

export const updateGoal = async (goalId, goalData) => {
  const res = await fetch(`${API_BASE_URL}/goals/${goalId}`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(goalData)
  });

  return parseJsonResponse(res);
};

export const deleteGoal = async (goalId) => {
  const res = await fetch(`${API_BASE_URL}/goals/${goalId}`, {
    method: "DELETE",
    headers: getAuthHeaders()
  });

  return parseJsonResponse(res);
};

export const contributeToGoal = async (
  goalId,
  amount,
  cycleId = null,
  contributionDate = null
) => {
  const res = await fetch(
    `${API_BASE_URL}/goals/${goalId}/contribute`,
    {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        amount,
        cycle_id: cycleId,
        contribution_date: contributionDate
      })
    }
  );

  return parseJsonResponse(res);
};

export const askAICoach = async (
  cycleId,
  question,
  historyDays = 5
) => {
  const res = await fetch(
    `${API_BASE_URL}/ml/shadow/cycle-coach/explanation`,
    {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        cycle_id: Number(cycleId),
        question,
        history_days: historyDays
      })
    }
  );

  return parseJsonResponse(res);
};

export const getAIChatHistory = async (cycleId, limit = 100) => {
  const res = await fetch(
    `${API_BASE_URL}/ml/coach/history?cycle_id=${cycleId}&limit=${limit}`,
    {
      headers: getAuthHeaders()
    }
  );

  return parseJsonResponse(res);
};

export const getPaymentSummary = async (cycleId) => {
  const res = await fetch(
    `${API_BASE_URL}/payment-summary?cycle_id=${cycleId}`,
    {
      headers: getAuthHeaders()
    }
  );

  return parseJsonResponse(res);
};

export const getCreditCards = async () => {
  const res = await fetch(`${API_BASE_URL}/credit-cards`, {
    headers: getAuthHeaders()
  });
  return parseJsonResponse(res);
};

export const createCreditCard = async (name) => {
  const res = await fetch(`${API_BASE_URL}/credit-cards`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ name })
  });
  return parseJsonResponse(res);
};

export const getCreditCardExpenses = async (cycleId) => {
  const res = await fetch(
    `${API_BASE_URL}/credit-card-expenses?cycle_id=${cycleId}`,
    { headers: getAuthHeaders() }
  );
  return parseJsonResponse(res);
};

export const updateCreditCardSettlement = async (expenseId, settled) => {
  const res = await fetch(
    `${API_BASE_URL}/expense/${expenseId}/settlement`,
    {
      method: "PATCH",
      headers: getAuthHeaders(),
      body: JSON.stringify({ settled })
    }
  );
  return parseJsonResponse(res);
};

// =========================
// DAILY TABLE
// =========================

export const getDailyTable = async (cycleId) => {
  const data = await getBudgetData(cycleId);
  return data.daily_table || [];
};

export const getBudgetData = async (cycleId) => {
  const res = await fetch(
    `${API_BASE_URL}/daily-table?cycle_id=${cycleId}`,
    {
      headers: getAuthHeaders()
    }
  );

  return res.json();
};

export const getDailyDetails = async (
  cycleId,
  expenseDate
) => {
  const res = await fetch(
    `${API_BASE_URL}/daily-details?cycle_id=${cycleId}&expense_date=${expenseDate}`,
    {
      headers: getAuthHeaders()
    }
  );

  return res.json();
};

// =========================
// EXPENSES
// =========================

export const createExpense = async (expenseData) => {
  const res = await fetch(`${API_BASE_URL}/expense`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(expenseData)
  });

  return parseJsonResponse(res);
};

export const updateExpense = async (
  expenseId,
  expenseData
) => {
  const res = await fetch(
    `${API_BASE_URL}/expense/${expenseId}`,
    {
      method: "PUT",
      headers: getAuthHeaders(),
      body: JSON.stringify(expenseData)
    }
  );

  return parseJsonResponse(res);
};

export const deleteExpense = async (
  expenseId
) => {
  const res = await fetch(
    `${API_BASE_URL}/expense/${expenseId}`,
    {
      method: "DELETE",
      headers: getAuthHeaders()
    }
  );

  return parseJsonResponse(res);
};

export const forgotPassword = async (email) => {
  const res = await fetch(
    `${API_BASE_URL}/forgot-password`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ email })
    }
  );

  return res.json();
};

export const resetPassword = async (
  token,
  newPassword
) => {
  const res = await fetch(
    `${API_BASE_URL}/reset-password`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        token,
        new_password: newPassword
      })
    }
  );

  return res.json();
};
