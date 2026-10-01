import Button from "./Button";

function CycleForm({
  cycleName,
  setCycleName,
  income,
  setIncome,
  startDate,
  setStartDate,
  endDate,
  setEndDate,
  handleCreateCycle,
  cycleLoading
}) {
  return (
    <div className="drawer-form">
      <label className="pulse-field">
        <span>Cycle name</span>
        <input
          className="expense-input"
          type="text"
          placeholder="Monthly income or trip"
          value={cycleName}
          onChange={(e) => setCycleName(e.target.value)}
        />
      </label>

      <label className="pulse-field">
        <span>Income</span>
        <input
          className="expense-input"
          type="number"
          min="0.01"
          step="0.01"
          placeholder="EGP"
          value={income}
          onChange={(e) => setIncome(e.target.value)}
        />
      </label>

      <label className="pulse-field">
        <span>Start date</span>
        <input
          className="expense-input"
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
        />
      </label>

      <label className="pulse-field">
        <span>End date</span>
        <input
          className="expense-input"
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
        />
      </label>

      <Button
        onClick={handleCreateCycle}
        disabled={cycleLoading}
      >
        {cycleLoading ? "Creating..." : "Create Cycle"}
      </Button>
    </div>
  );
}

export default CycleForm;
