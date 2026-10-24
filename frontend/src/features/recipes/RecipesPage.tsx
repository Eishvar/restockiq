import RecipeBook from './RecipeBook'

export default function RecipesPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Recipes</h1>
        <p className="mt-1 text-sm text-slate-600">
          What goes into one serving of each dish. The forecast says how many dishes you will sell; these amounts turn that into the
          ingredients you need to buy. A dish without a recipe cannot be planned. Changes are used the next time you generate a plan.
        </p>
      </div>
      <RecipeBook />
    </div>
  )
}
