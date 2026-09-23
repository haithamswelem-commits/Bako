import { useState } from "react";

import Button from "./Button";
import { formatSubcategoryName } from "../utils/displayNames";

const normalizeChoiceName = (value) => value.trim().replace(/\s+/g, " ");
const choiceNameHasLetter = (value) => /\p{L}/u.test(value);

function ExpenseForm({
  amount,
  setAmount,
  description,
  setDescription,
  selectedCategory,
  setSelectedCategory,
  selectedSubcategory,
  setSelectedSubcategory,
  paymentChannel,
  setPaymentChannel,
  creditCards = [],
  selectedCreditCard,
  setSelectedCreditCard,
  newCreditCardName,
  setNewCreditCardName,
  onCreateCreditCard,
  expenseDate,
  setExpenseDate,
  categories,
  subcategories,
  handleSubmit,
  expenseLoading,
  onCreateCategory,
  onCreateSubcategory,
  onRenameCategory,
  onArchiveCategory,
  onRenameSubcategory,
  onArchiveSubcategory,
  onSuggestCategory,
  onUseSuggestedCategoryPair,
  onCreateSuggestedCategoryPair,
  onConfirm,
  lockedDate = false
}) {
  const [newCategoryName, setNewCategoryName] = useState("");
  const [newSubcategoryName, setNewSubcategoryName] = useState("");
  const [showNewCategory, setShowNewCategory] = useState(false);
  const [showNewSubcategory, setShowNewSubcategory] = useState(false);
  const [categoryRename, setCategoryRename] = useState("");
  const [subcategoryRename, setSubcategoryRename] = useState("");
  const [showCategoryRename, setShowCategoryRename] = useState(false);
  const [showSubcategoryRename, setShowSubcategoryRename] = useState(false);
  const [optionLoading, setOptionLoading] = useState(false);
  const [optionError, setOptionError] = useState("");
  const [suggestionLoading, setSuggestionLoading] = useState(false);
  const [suggestionResult, setSuggestionResult] = useState(null);
  const [categorizationSuggestionId, setCategorizationSuggestionId] = useState(null);
  const [showManualChoices, setShowManualChoices] = useState(false);
  const [showNewCreditCard, setShowNewCreditCard] = useState(false);

  const requestSuggestion = async () => {
    const normalized = description.trim().replace(/\s+/g, " ");
    if (normalized.length < 2 || !choiceNameHasLetter(normalized)) {
      setSuggestionResult({
        type: "error",
        message: "Describe the expense using at least one letter."
      });
      return;
    }

    try {
      setSuggestionLoading(true);
      setSuggestionResult(null);
      setCategorizationSuggestionId(null);
      const response = await onSuggestCategory(normalized);
      setCategorizationSuggestionId(response.suggestion_event_id || null);
      if (!response.suggestion) {
        setSuggestionResult({
          type: response.proposal ? "proposal" : "neutral",
          message: response.message,
          proposal: response.proposal
        });
        return;
      }
      setSuggestionResult({
        type: "success",
        message: response.message,
        suggestion: response.suggestion
      });
    } catch (error) {
      setSuggestionResult({
        type: "error",
        message: error.message || "Could not prepare a suggestion."
      });
    } finally {
      setSuggestionLoading(false);
    }
  };

  const useSuggestion = async () => {
    const suggestion = suggestionResult?.suggestion;
    const proposal = suggestionResult?.proposal;
    if (!suggestion && !proposal) return;

    try {
      setOptionLoading(true);
      setOptionError("");
      if (proposal) {
        await onCreateSuggestedCategoryPair(proposal);
      } else {
        await onUseSuggestedCategoryPair(suggestion);
      }
      setSuggestionResult({
        type: "success",
        message: "Selected. You can now add the expense.",
        suggestion: proposal
          ? { ...proposal, source: "llm" }
          : suggestion,
        selected: true
      });
      setShowManualChoices(false);
    } catch (error) {
      setOptionError(error.message || "Could not use this suggestion");
    } finally {
      setOptionLoading(false);
    }
  };

  const chooseManually = () => {
    setShowManualChoices(true);
    setSuggestionResult(null);
    setOptionError("");
  };

  const addCategory = async () => {
    const name = normalizeChoiceName(newCategoryName);
    if (!choiceNameHasLetter(name)) {
      setOptionError("Where the money went must include at least one letter");
      return;
    }
    try {
      setOptionLoading(true);
      setOptionError("");
      await onCreateCategory(name);
      setNewCategoryName("");
      setShowNewCategory(false);
    } catch (error) {
      setOptionError(error.message || "Could not add spending group");
    } finally {
      setOptionLoading(false);
    }
  };

  const addSubcategory = async () => {
    const name = normalizeChoiceName(newSubcategoryName);
    if (!choiceNameHasLetter(name)) {
      setOptionError("What kind must include at least one letter");
      return;
    }
    if (!selectedCategory) return;
    try {
      setOptionLoading(true);
      setOptionError("");
      await onCreateSubcategory(name);
      setNewSubcategoryName("");
      setShowNewSubcategory(false);
    } catch (error) {
      setOptionError(error.message || "Could not add expense type");
    } finally {
      setOptionLoading(false);
    }
  };

  const selectedCategoryOption = categories.find(
    (category) => String(category.id) === String(selectedCategory)
  );
  const selectedSubcategoryOption = subcategories.find(
    (subcategory) => String(subcategory.id) === String(selectedSubcategory)
  );

  const renameCategory = async () => {
    const name = normalizeChoiceName(categoryRename);
    if (!choiceNameHasLetter(name)) {
      setOptionError("Where the money went must include at least one letter");
      return;
    }
    if (!selectedCategory) return;
    try {
      setOptionLoading(true);
      setOptionError("");
      await onRenameCategory(selectedCategory, name);
      setShowCategoryRename(false);
      setCategoryRename("");
    } catch (error) {
      setOptionError(error.message || "Could not rename spending group");
    } finally {
      setOptionLoading(false);
    }
  };

  const removeCategory = async () => {
    if (!selectedCategory) return;
    const confirmed = await onConfirm?.({
      title: "Remove spending group?",
      message: "It will disappear from future expenses. Past expenses will stay unchanged.",
      confirmLabel: "Remove"
    });
    if (!confirmed) return;
    try {
      setOptionLoading(true);
      setOptionError("");
      await onArchiveCategory(selectedCategory);
      setShowCategoryRename(false);
      setShowSubcategoryRename(false);
    } catch (error) {
      setOptionError(error.message || "Could not remove spending group");
    } finally {
      setOptionLoading(false);
    }
  };

  const renameSubcategory = async () => {
    const name = normalizeChoiceName(subcategoryRename);
    if (!choiceNameHasLetter(name)) {
      setOptionError("What kind must include at least one letter");
      return;
    }
    if (!selectedSubcategory) return;
    try {
      setOptionLoading(true);
      setOptionError("");
      await onRenameSubcategory(
        selectedSubcategory,
        name
      );
      setShowSubcategoryRename(false);
      setSubcategoryRename("");
    } catch (error) {
      setOptionError(error.message || "Could not rename expense type");
    } finally {
      setOptionLoading(false);
    }
  };

  const removeSubcategory = async () => {
    if (!selectedSubcategory) return;
    const confirmed = await onConfirm?.({
      title: "Remove expense type?",
      message: "It will disappear from future expenses. Past expenses will stay unchanged.",
      confirmLabel: "Remove"
    });
    if (!confirmed) return;
    try {
      setOptionLoading(true);
      setOptionError("");
      await onArchiveSubcategory(selectedSubcategory);
      setShowSubcategoryRename(false);
    } catch (error) {
      setOptionError(error.message || "Could not remove expense type");
    } finally {
      setOptionLoading(false);
    }
  };

  return (
    <div className="expense-form">
      <div className="expense-primary-fields">
        <label className="pulse-field expense-row-field">
          <span>Amount</span>
          <input
            className="expense-input"
            type="number"
            min="0.01"
            step="0.01"
            placeholder="EGP"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </label>

        <div className="expense-description-field expense-row-field">
          <label htmlFor="expense-description">What did you pay for?</label>
          <input
            id="expense-description"
            className="expense-input"
            type="text"
            placeholder="Example: Uber ride home"
            value={description}
            maxLength={200}
            onChange={(event) => {
              setDescription(event.target.value);
              if (suggestionResult?.selected) {
                setSelectedCategory("");
                setSelectedSubcategory("");
              }
              setSuggestionResult(null);
              setCategorizationSuggestionId(null);
            }}
          />
        </div>
      </div>

      <div className="expense-categorizer-actions">
          <button
            type="button"
            className="expense-suggest-button"
            onClick={requestSuggestion}
            disabled={suggestionLoading}
          >
            {suggestionLoading ? "Checking..." : "Suggest where it belongs"}
          </button>
          <button
            type="button"
            className="expense-choose-myself"
            onClick={chooseManually}
          >
            Choose myself
          </button>
      </div>
      {suggestionResult && (
          <div
            className={`expense-category-suggestion is-${suggestionResult.type}`}
            role="status"
          >
            {suggestionResult.suggestion && (
              <strong>
                {suggestionResult.suggestion.category_name}
                {" / "}
                {suggestionResult.suggestion.subcategory_name}
              </strong>
            )}
            {suggestionResult.proposal && (
              <>
                <strong>
                  {suggestionResult.proposal.category_name}
                  {" / "}
                  {suggestionResult.proposal.subcategory_name}
                </strong>
              </>
            )}
            <span>{suggestionResult.message}</span>
            {(suggestionResult.suggestion || suggestionResult.proposal) &&
              !suggestionResult.selected && (
                <div className="expense-suggestion-actions">
                  <button
                    type="button"
                    className="expense-suggestion-create"
                    onClick={useSuggestion}
                    disabled={optionLoading}
                  >
                    {optionLoading ? "Applying..." : "Use this"}
                  </button>
                  <button
                    type="button"
                    className="expense-suggestion-change"
                    onClick={chooseManually}
                    disabled={optionLoading}
                  >
                    Change
                  </button>
                </div>
              )}
          </div>
      )}

      {showManualChoices && (
        <div className="expense-manual-choices">
          <div className="expense-choice-field">
        <label htmlFor="expense-category">Where did the money go?</label>
        <div className="expense-choice-row">
          <select
            id="expense-category"
            className="expense-input"
            value={selectedCategory}
            onChange={(event) => {
              setSelectedCategory(event.target.value);
              setShowCategoryRename(false);
              setShowSubcategoryRename(false);
              setCategoryRename("");
              setSubcategoryRename("");
            }}
          >
            <option value="">Choose where it went</option>

            {categories.map((cat) => (
              <option key={cat.id} value={cat.id}>
                {cat.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="expense-choice-add"
            onClick={() => {
              setShowNewCategory((current) => !current);
              setShowCategoryRename(false);
            }}
          >
            + Add
          </button>
        </div>
        {showNewCategory && (
          <div className="expense-choice-create">
            <input
              className="expense-input"
              value={newCategoryName}
              onChange={(event) => setNewCategoryName(event.target.value)}
              placeholder="Example: Home"
              maxLength={100}
            />
            <button type="button" onClick={addCategory} disabled={optionLoading}>
              Add
            </button>
          </div>
        )}
        {selectedCategoryOption && !showNewCategory && (
          <div className="expense-choice-manage">
            <button
              type="button"
              onClick={() => {
                setCategoryRename(selectedCategoryOption.name);
                setShowCategoryRename((current) => !current);
              }}
              disabled={optionLoading}
            >
              Rename
            </button>
            <button
              type="button"
              className="is-remove"
              onClick={removeCategory}
              disabled={optionLoading}
            >
              Remove
            </button>
          </div>
        )}
        {showCategoryRename && selectedCategoryOption && (
          <div className="expense-choice-create">
            <input
              className="expense-input"
              value={categoryRename}
              onChange={(event) => setCategoryRename(event.target.value)}
              maxLength={100}
              aria-label="Rename spending group"
            />
            <button type="button" onClick={renameCategory} disabled={optionLoading}>
              Save
            </button>
          </div>
        )}
          </div>

          <div className="expense-choice-field">
        <label htmlFor="expense-subcategory">What kind?</label>
        <div className="expense-choice-row">
          <select
            id="expense-subcategory"
            className="expense-input"
            value={selectedSubcategory}
            onChange={(event) => {
              setSelectedSubcategory(event.target.value);
              setShowSubcategoryRename(false);
              setSubcategoryRename("");
            }}
            disabled={!selectedCategory}
          >
            <option value="">Choose what kind</option>

            {subcategories.map((sub) => (
              <option key={sub.id} value={sub.id}>
                {formatSubcategoryName(sub.name)}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="expense-choice-add"
            onClick={() => {
              setShowNewSubcategory((current) => !current);
              setShowSubcategoryRename(false);
            }}
            disabled={!selectedCategory}
          >
            + Add
          </button>
        </div>
        {showNewSubcategory && selectedCategory && (
          <div className="expense-choice-create">
            <input
              className="expense-input"
              value={newSubcategoryName}
              onChange={(event) => setNewSubcategoryName(event.target.value)}
              placeholder="Example: Building maintenance"
              maxLength={100}
            />
            <button type="button" onClick={addSubcategory} disabled={optionLoading}>
              Add
            </button>
          </div>
        )}
        {selectedSubcategoryOption && !showNewSubcategory && (
          <div className="expense-choice-manage">
            <button
              type="button"
              onClick={() => {
                setSubcategoryRename(selectedSubcategoryOption.name);
                setShowSubcategoryRename((current) => !current);
              }}
              disabled={optionLoading}
            >
              Rename
            </button>
            <button
              type="button"
              className="is-remove"
              onClick={removeSubcategory}
              disabled={optionLoading}
            >
              Remove
            </button>
          </div>
        )}
        {showSubcategoryRename && selectedSubcategoryOption && (
          <div className="expense-choice-create">
            <input
              className="expense-input"
              value={subcategoryRename}
              onChange={(event) => setSubcategoryRename(event.target.value)}
              maxLength={100}
              aria-label="Rename expense type"
            />
            <button type="button" onClick={renameSubcategory} disabled={optionLoading}>
              Save
            </button>
          </div>
        )}
          </div>
        </div>
      )}

      {optionError && (
        <p className="expense-choice-error" role="alert">{optionError}</p>
      )}

      <div className="expense-secondary-fields">
        {!lockedDate && (
          <label className="pulse-field expense-row-field">
            <span>Date</span>
            <input
              className="expense-input"
              type="date"
              value={expenseDate}
              onChange={(e) => setExpenseDate(e.target.value)}
            />
          </label>
        )}

        <label className="pulse-field expense-row-field">
          <span>Payment method</span>
          <select
            className="expense-input"
            value={paymentChannel}
            onChange={(event) => setPaymentChannel(event.target.value)}
          >
            <option value="cash">Cash</option>
            <option value="credit_card">Credit Card</option>
          </select>
        </label>

        {paymentChannel === "credit_card" && (
          <>
            <div className="expense-card-choice">
              <select
                className="expense-input"
                value={selectedCreditCard}
                onChange={(event) => setSelectedCreditCard(event.target.value)}
                aria-label="Credit card"
              >
                <option value="">Unassigned card</option>
                {creditCards.map((card) => (
                  <option key={card.id} value={card.id}>{card.name}</option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => setShowNewCreditCard((current) => !current)}
                aria-expanded={showNewCreditCard}
              >
                + Add card
              </button>
            </div>
            {showNewCreditCard && (
              <div className="expense-choice-create expense-card-create">
                <input
                  className="expense-input"
                  value={newCreditCardName}
                  onChange={(event) => setNewCreditCardName(event.target.value)}
                  placeholder="Card name"
                  maxLength={100}
                />
                <button
                  type="button"
                  onClick={async () => {
                    const created = await onCreateCreditCard();
                    if (created) setShowNewCreditCard(false);
                  }}
                  disabled={!newCreditCardName.trim()}
                >
                  Add
                </button>
              </div>
            )}
          </>
        )}
      </div>

      <Button
        onClick={() => handleSubmit({ categorizationSuggestionId })}
        disabled={
          expenseLoading ||
          !amount ||
          !selectedCategory ||
          !selectedSubcategory
        }
      >
        {expenseLoading ? "Adding..." : "Add Expense"}
      </Button>
    </div>
  );
}

export default ExpenseForm;
