
# Future Features

## Cost Tracking and Trend Analysis

### Business Intelligence Features
- Track ingredient cost changes over time
- Record historical price points for each inventory item
- Calculate recipe cost trends based on ingredient price fluctuations
- Compare product pricing vs ingredient cost trends
- Monitor profit margin changes automatically

### Data Collection Requirements
- Store timestamp with each inventory cost update
- Track FIFO inventory costs separately
- Log batch production costs with timestamps
- Record product sale prices over time

### AI Analysis Features
- Detect significant cost increases in ingredients
- Predict future cost trends
- Suggest product price adjustments
- Alert on declining profit margins
- Recommend recipe modifications based on cost
- Generate cost optimization reports

### Database Additions Needed
- Historical price tables
- Cost trend tracking
- Margin analysis tables
- AI recommendation logs

### Integration Points
- Connect with FIFO system
- Link to batch production
- Interface with product pricing
- Integrate with inventory updates

### Comunity for makers
- sell m-m maker to maker
- recipies? process?
- ability to upload recipies in certain format
-
## Augmentation in Batch In Progress (Pre-Finish Split)
Split the batch while it's still open — ideal for cases where a maker adds scents, colors, or other tweaks after cooking but before containerizing.

🧭 1. Prompt in Batch In Progress Page
Trigger UI Option:

“Would you like to augment this batch?”

Appears:

After timer or cooking step

Or near the notes/labels area in BIP

🔄 2. Two Split Modes
🟢 Augment Entire Batch
→ Entire base yield is assigned to augmentations. No remaining base batch left.

🟡 Augment Portions
→ Only part of the batch is split. The rest remains under the original label and finish path.

🧪 3. Augmentation UI Structure
Once augmentation is triggered, show:

Augmented Batch Label	% of Total Yield	Added Ingredients (e.g., scent)	Containers
101A (Lavender)	50%	Lavender EO 1.5g	2 x 4oz Jars
101B (Rose)	50%	Rose EO 2g	1 x 5oz Jar

+ Add Augmentation

Validation: Total % must equal 100%

Optional: auto-split containers proportionally or allow manual override

📦 4. Containers Integration
Let augmentations inherit container pool from base BIP plan

Assign each container explicitly to one augmentation OR auto-divide based on % yield

If user changes containers mid-batch → show updated container pool in augmentation view

🔗 5. Inventory Flow
Ingredients added (like scents) → deducted with proper cost & unit logic

Containers assigned → show up in final product inventory per augmentation

Each augmented batch gets:

batch_id like 101A, 101B

Linked back to original with parent_batch_id = 101

📘 6. Finish Batch Becomes Simple
After augmenting in BIP:

Each sub-batch enters its own Finish Batch modal

User selects final product or variant for each (or uses quick-pass if auto-linked)

🧠 Why This Approach Works Well
Realistic to how makers add fragrance after cook/cool

Avoids needing duplicate recipes for every scent variation

Preserves the integrity and traceability of the base recipe

Allows flexibility but avoids messiness of “augment later” logic

