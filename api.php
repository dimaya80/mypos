<?php
header("Content-Type: application/json");
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: GET, POST");

ini_set('memory_limit', '256M');
ini_set('max_execution_time', 60);

error_log("API version: 2025-06-30-timbang-fix");

// Database connection
$host = "localhost";
$username = "root";
$password = "";
$database = "mypos";

$conn = new mysqli($host, $username, $password, $database);
if ($conn->connect_error) {
    error_log("Database connection failed: " . $conn->connect_error);
    echo json_encode(["status" => "error", "message" => "Connection failed: " . $conn->connect_error]);
    exit();
}

$data = [];
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $raw_input = file_get_contents("php://input");
    error_log("Raw POST input: " . $raw_input);
    $data = json_decode($raw_input, true);
    if (json_last_error() !== JSON_ERROR_NONE) {
        echo json_encode(["status" => "error", "message" => "Invalid JSON format: " . json_last_error_msg()]);
        error_log("JSON parse error: " . json_last_error_msg());
        exit;
    }
}

// LOGIN USER
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($data['action']) && $data['action'] == 'login') {
    if (!isset($data['username']) || !isset($data['password'])) {
        echo json_encode(["status" => "error", "message" => "Username and password required"]);
        exit;
    }
    $username = trim($data['username']);
    $password = $data['password'];
    $sql = "SELECT id, username, password, role FROM users WHERE username = ?";
    $stmt = $conn->prepare($sql);
    $stmt->bind_param("s", $username);
    $stmt->execute();
    $result = $stmt->get_result();
    if ($result->num_rows > 0) {
        $user = $result->fetch_assoc();
        if (password_verify($password, $user['password'])) {
            echo json_encode([
                "status" => "success",
                "user" => [
                    "id" => $user['id'],
                    "username" => $user['username'],
                    "role" => $user['role'] ?? "user"
                ],
                "message" => "Login successful"
            ]);
        } else {
            echo json_encode(["status" => "error", "message" => "Invalid credentials"]);
        }
    } else {
        echo json_encode(["status" => "error", "message" => "User not found"]);
    }
    $stmt->close();
}

// SAVE TRANSACTION (Timbang Ready)
elseif ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($data['action']) && $data['action'] == 'save_transaction') {
    $conn->begin_transaction();
    try {
        $required_fields = ['user_id', 'items', 'total', 'discount', 'amount_paid', 'payment_method_id', 'payment_method'];
        foreach ($required_fields as $field) {
            if (!isset($data[$field])) throw new Exception("Missing required field: $field");
        }
        $receipt_no = "INV" . date("Ymd") . str_pad(mt_rand(1, 9999), 4, '0', STR_PAD_LEFT);
        $payment_method_id = (int)$data['payment_method_id'];
        $payment_method_text = $conn->real_escape_string($data['payment_method']);
        $user_id = (int)$data['user_id'];
        $total = (float)$data['total'];
        $discount = (float)$data['discount'];
        $amount_paid = (float)$data['amount_paid'];
        $change = $amount_paid - $total;

        $stmt = $conn->prepare("INSERT INTO sales (receipt_no, sale_date, user_id, total, discount, payment_received, change_given, payment_method_id) VALUES (?, NOW(), ?, ?, ?, ?, ?, ?)");
        $stmt->bind_param("siddddi", $receipt_no, $user_id, $total, $discount, $amount_paid, $change, $payment_method_id);
        $stmt->execute();
        $sale_id = $conn->insert_id;
        $stmt->close();

        foreach ($data['items'] as $item) {
            $item_name = $conn->real_escape_string($item['name']);
            $quantity = (float)$item['quantity']; // BENARKAN FLOAT UNTUK TIMBANG
            $unit_price = round((float)$item['price'], 4);
            $total_price = round((float)$item['total'], 4);

            $stmt = $conn->prepare("SELECT i.id FROM items i WHERE i.item_name = ? LIMIT 1");
            $stmt->bind_param("s", $item_name);
            $stmt->execute();
            $result = $stmt->get_result();
            $item_data = $result->fetch_assoc();
            $item_id = $item_data ? (int)$item_data['id'] : null;
            $stmt->close();

            if ($item_id) {
                $stmt = $conn->prepare("INSERT INTO sales_items (sale_id, item_id, quantity, unit_price, total_price) VALUES (?, ?, ?, ?, ?)");
                $stmt->bind_param("iiddd", $sale_id, $item_id, $quantity, $unit_price, $total_price);
                $stmt->execute();
                $stmt->close();
            } else {
                throw new Exception("Item not found: $item_name");
            }
        }

        // Option: Simpan customer_credit jika payment_method_id == 2 dan ada customer_info
        if ($payment_method_id == 2 && isset($data['customer_info'])) {
            $customer_info = $data['customer_info'];
            $customer_name = $conn->real_escape_string($customer_info['name'] ?? '');
            $phone = $conn->real_escape_string($customer_info['phone'] ?? '');
            $address = $conn->real_escape_string($customer_info['address'] ?? '');
            $stmt = $conn->prepare("INSERT INTO customer_credit (sale_id, customer_name, phone, address, amount, due_date) VALUES (?, ?, ?, ?, ?, DATE_ADD(NOW(), INTERVAL 30 DAY))");
            $stmt->bind_param("isssd", $sale_id, $customer_name, $phone, $address, $total);
            $stmt->execute();
            $stmt->close();
        }

        // Update shift cash_end jika tunai
        if ($payment_method_id == 1) {
            $shift_query = "SELECT id, cash_end FROM shifts WHERE user_id = ? AND shift_end IS NULL ORDER BY shift_start DESC LIMIT 1";
            $shift_stmt = $conn->prepare($shift_query);
            $shift_stmt->bind_param("i", $user_id);
            $shift_stmt->execute();
            $shift_result = $shift_stmt->get_result();
            if ($shift_result->num_rows > 0) {
                $shift = $shift_result->fetch_assoc();
                $new_cash_end = $shift['cash_end'] + $total;
                $update_query = "UPDATE shifts SET cash_end = ? WHERE id = ?";
                $update_stmt = $conn->prepare($update_query);
                $update_stmt->bind_param("di", $new_cash_end, $shift['id']);
                $update_stmt->execute();
                $update_stmt->close();
            }
            $shift_stmt->close();
        }

        $conn->commit();
        echo json_encode([
            'status' => 'success',
            'message' => 'Transaction saved successfully',
            'data' => [
                'receipt_no' => $receipt_no,
                'sale_id' => $sale_id,
                'payment_method' => $payment_method_text,
                'total' => $total,
                'discount' => $discount,
                'amount_paid' => $amount_paid,
                'change_given' => $change
            ]
        ]);
    } catch (Exception $e) {
        $conn->rollback();
        echo json_encode([
            'status' => 'error',
            'message' => 'Transaction failed: ' . $e->getMessage()
        ]);
    }
}

// GET LOW STOCK PRODUCTS
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action']) && $_GET['action'] == 'get_low_stock_products') {
    $threshold = 5;

    $sql = "SELECT 
                i.id,
                i.item_name as name,
                (SELECT sp.supplier_price_unit 
                 FROM supplier_prices sp 
                 WHERE sp.item_id = i.id 
                 ORDER BY sp.date_keyin DESC 
                 LIMIT 1) as price,
                i.barcode_per_unit as barcode,
                (COALESCE(SUM(sp.stock_per_unit), 0) - 
                COALESCE((SELECT SUM(si.quantity) 
                         FROM sales_items si
                         JOIN sales s ON si.sale_id = s.id
                         WHERE si.item_id = i.id), 0)) as stock
            FROM items i
            LEFT JOIN supplier_prices sp ON i.id = sp.item_id
            GROUP BY i.id
            HAVING stock <= ?
            ORDER BY stock ASC";

    $stmt = $conn->prepare($sql);
    if (!$stmt) {
        echo json_encode(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
        error_log("Get low stock products error: Prepare failed - " . $conn->error);
        exit;
    }
    $stmt->bind_param("i", $threshold);
    $stmt->execute();
    $result = $stmt->get_result();

    $products = [];
    while ($row = $result->fetch_assoc()) {
        $products[] = [
            'id' => $row['id'],
            'name' => $row['name'],
            'price' => $row['price'],
            'barcode' => $row['barcode'],
            'stock' => (int)$row['stock'],
            'status' => ($row['stock'] <= 0) ? 'HABIS' : 'KRITIKAL'
        ];
    }

    echo json_encode([
        'status' => 'success',
        'products' => $products
    ]);

    $stmt->close();
}

// GET PRODUCT BY BARCODE
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['barcode'])) {
    $barcode = $_GET['barcode'];
    $sql = "SELECT 
               i.id, 
               i.item_name as name, 
               (SELECT sp.supplier_price_unit 
                FROM supplier_prices sp 
                WHERE sp.item_id = i.id 
                ORDER BY sp.date_keyin DESC 
                LIMIT 1) as price,
               i.barcode_per_unit,
               i.is_weighable,
               i.unit_of_measurement
            FROM items i
            WHERE i.barcode_per_unit = ? OR 
                  i.barcode_per_pack = ? OR 
                  i.barcode_per_box = ?
            LIMIT 1";

    $stmt = $conn->prepare($sql);
    if (!$stmt) {
        echo json_encode(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
        error_log("Get product by barcode error: Prepare failed - " . $conn->error);
        exit;
    }
    $stmt->bind_param("sss", $barcode, $barcode, $barcode);
    $stmt->execute();
    $result = $stmt->get_result();

    $product = $result->fetch_assoc();
    if ($product) {
        echo json_encode([
            'id' => $product['id'],
            'name' => $product['name'],
            'price' => $product['price'],
            'barcode' => $product['barcode_per_unit'],
            'is_weighable' => isset($product['is_weighable']) ? (int)$product['is_weighable'] : 0,
            'unit_of_measurement' => $product['unit_of_measurement'] ?? ''
        ]);
    } else {
        echo json_encode(["error" => "Product not found"]);
    }
    $stmt->close();
}

// SEARCH PRODUCTS
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && (isset($_GET['search']) || (isset($_GET['action']) && $_GET['action'] == 'search_products'))) {
    $search_term = isset($_GET['search']) ? $_GET['search'] : (isset($_GET['query']) ? $_GET['query'] : '');
    $search = "%" . $conn->real_escape_string($search_term) . "%";
    $limit = isset($_GET['limit']) ? (int)$_GET['limit'] : 50;

    $sql = "SELECT 
                i.id, 
                i.item_name as name, 
                latest_price.supplier_price_unit as price,
                i.barcode_per_unit as barcode,
                (COALESCE(total_stock.stock_per_unit, 0) - 
                 COALESCE(total_sales.quantity, 0)) as stock,
                i.is_weighable,
                i.unit_of_measurement
            FROM items i
            LEFT JOIN (
                SELECT item_id, MAX(date_keyin) as max_date
                FROM supplier_prices
                GROUP BY item_id
            ) latest_date ON i.id = latest_date.item_id
            LEFT JOIN supplier_prices latest_price ON 
                latest_price.item_id = latest_date.item_id AND 
                latest_price.date_keyin = latest_date.max_date
            LEFT JOIN (
                SELECT item_id, SUM(stock_per_unit) as stock_per_unit
                FROM supplier_prices
                GROUP BY item_id
            ) total_stock ON i.id = total_stock.item_id
            LEFT JOIN (
                SELECT si.item_id, SUM(si.quantity) as quantity
                FROM sales_items si
                JOIN sales s ON si.sale_id = s.id
                GROUP BY si.item_id
            ) total_sales ON i.id = total_sales.item_id
            WHERE i.item_name LIKE ?
            ORDER BY 
                CASE 
                    WHEN i.item_name LIKE ? THEN 0
                    WHEN i.item_name LIKE ? THEN 1
                    ELSE 2
                END,
                i.item_name
            LIMIT ?";

    $stmt = $conn->prepare($sql);
    if (!$stmt) {
        echo json_encode(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
        error_log("Search products error: Prepare failed - " . $conn->error);
        exit;
    }

    $exact_match = $conn->real_escape_string($search_term) . "%";
    $starts_with = $conn->real_escape_string($search_term) . "%";
    $stmt->bind_param("sssi", $search, $exact_match, $starts_with, $limit);

    if (!$stmt->execute()) {
        echo json_encode(['status' => 'error', 'message' => 'Execute failed: ' . $stmt->error]);
        error_log("Search products error: Execute failed - " . $stmt->error);
        exit;
    }

    $result = $stmt->get_result();

    $products = [];
    while ($row = $result->fetch_assoc()) {
        $products[] = [
            'id' => (int)$row['id'],
            'name' => $row['name'],
            'price' => (float)$row['price'],
            'barcode' => $row['barcode'],
            'stock' => (int)$row['stock'],
            'is_weighable' => isset($row['is_weighable']) ? (int)$row['is_weighable'] : 0,
            'unit_of_measurement' => $row['unit_of_measurement'] ?? ''
        ];
    }

    echo json_encode([
        'status' => 'success',
        'data' => $products,
        'count' => count($products)
    ]);

    $stmt->close();
}

// GET SHIFT INFO (tambah kod ini dalam api.php!)
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action']) && $_GET['action'] == 'check_shift' && isset($_GET['user_id'])) {
    $user_id = (int)$_GET['user_id'];
    $sql = "SELECT s.cash_start, s.cash_end, s.shift_start, u.username AS cashier_name
            FROM shifts s
            LEFT JOIN users u ON s.user_id = u.id
            WHERE s.user_id = ? AND s.shift_end IS NULL
            ORDER BY s.shift_start DESC LIMIT 1";
    $stmt = $conn->prepare($sql);
    $stmt->bind_param("i", $user_id);
    $stmt->execute();
    $result = $stmt->get_result();
    if ($row = $result->fetch_assoc()) {
        echo json_encode([
            'status' => 'success',
            'has_shift' => true,
            'shift_data' => [
                'cashier_name' => $row['cashier_name'],
                'shift_start' => $row['shift_start'],
                'cash_start' => (float)$row['cash_start'],
                'cash_end' => (float)$row['cash_end']
            ]
        ]);
    } else {
        echo json_encode([
            'status' => 'success',
            'has_shift' => false
        ]);
    }
    $stmt->close();
}

// GET TODAY'S SALES
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action']) && $_GET['action'] == 'get_today_sales' && isset($_GET['date'])) {
    $date = $_GET['date'];
    error_log("Get today's sales: date=$date");

    if (!DateTime::createFromFormat('Y-m-d', $date)) {
        echo json_encode([
            'status' => 'error',
            'message' => 'Invalid date format. Please use YYYY-MM-DD format'
        ]);
        error_log("Get today's sales error: Invalid date format for date=$date");
        exit;
    }

    $sql = "SELECT 
                @row_number:=@row_number+1 AS no,
                s.receipt_no,
                DATE_FORMAT(s.sale_date, '%Y-%m-%d %H:%i:%s') as sale_time,
                s.total,
                s.discount,
                s.payment_received as amount_paid,
                s.change_given,
                pm.method_name as payment_method,
                CASE 
                    WHEN cc.id IS NULL THEN 'Lunas' 
                    ELSE 'Hutang' 
                END as status
            FROM sales s
            LEFT JOIN payment_methods pm ON s.payment_method_id = pm.id
            LEFT JOIN customer_credit cc ON s.id = cc.sale_id,
            (SELECT @row_number:=0) AS t
            WHERE s.sale_date >= ? AND s.sale_date < DATE_ADD(?, INTERVAL 1 DAY)
            ORDER BY s.sale_date DESC";

    $stmt = $conn->prepare($sql);
    if (!$stmt) {
        echo json_encode(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
        error_log("Get today's sales error: Prepare failed - " . $conn->error);
        exit;
    }
    $stmt->bind_param("ss", $date, $date);
    $stmt->execute();
    $result = $stmt->get_result();

    $sales = [];
    while ($row = $result->fetch_assoc()) {
        $sales[] = [
            'no' => $row['no'],
            'receipt_no' => $row['receipt_no'],
            'sale_time' => $row['sale_time'],
            'total' => number_format($row['total'], 2),
            'discount' => number_format($row['discount'], 2),
            'amount_paid' => number_format($row['amount_paid'], 2),
            'change_given' => number_format($row['change_given'], 2),
            'payment_method' => $row['payment_method'],
            'status' => $row['status']
        ];
    }

    echo json_encode([
        'status' => 'success',
        'data' => $sales
    ]);

    $stmt->close();
}

// CHECK STOCK
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action']) && $_GET['action'] == 'check_stock') {
    $product_name = $_GET['product'];

    $sql = "SELECT id FROM items WHERE item_name = ?";
    $stmt = $conn->prepare($sql);
    if (!$stmt) {
        echo json_encode(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
        error_log("Check stock error: Prepare failed - " . $conn->error);
        exit;
    }
    $stmt->bind_param("s", $product_name);
    $stmt->execute();
    $result = $stmt->get_result();

    if ($result->num_rows > 0) {
        $item = $result->fetch_assoc();
        $item_id = $item['id'];

        $sql_stock = "SELECT COALESCE(SUM(stock_per_unit), 0) as total_stock 
                      FROM supplier_prices 
                      WHERE item_id = ?";
        $stmt_stock = $conn->prepare($sql_stock);
        if (!$stmt_stock) {
            echo json_encode(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
            error_log("Check stock error: Prepare failed for stock - " . $conn->error);
            exit;
        }
        $stmt_stock->bind_param("i", $item_id);
        $stmt_stock->execute();
        $result_stock = $stmt_stock->get_result();
        $stock_data = $result_stock->fetch_assoc();
        $total_stock = $stock_data['total_stock'];

        $sql_sold = "SELECT COALESCE(SUM(quantity), 0) as total_sold 
                     FROM sales_items 
                     WHERE item_id = ?";
        $stmt_sold = $conn->prepare($sql_sold);
        if (!$stmt_sold) {
            echo json_encode(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
            error_log("Check stock error: Prepare failed for sold - " . $conn->error);
            exit;
        }
        $stmt_sold->bind_param("i", $item_id);
        $stmt_sold->execute();
        $result_sold = $stmt_sold->get_result();
        $sold_data = $result_sold->fetch_assoc();
        $total_sold = $sold_data['total_sold'];

        $current_stock = $total_stock - $total_sold;

        echo json_encode([
            'status' => 'success',
            'stock' => (int)$current_stock
        ]);

        $stmt_stock->close();
        $stmt_sold->close();
    } else {
        echo json_encode([
            'status' => 'error',
            'message' => 'Product not found'
        ]);
    }

    $stmt->close();
}

// GET TRANSACTION DETAILS
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action']) && $_GET['action'] == 'get_transaction' && isset($_GET['receipt_no'])) {
    $receipt_no = $_GET['receipt_no'];

    $sql = "SELECT 
                s.id,
                s.receipt_no,
                DATE_FORMAT(s.sale_date, '%Y-%m-%d %H:%i:%s') as sale_date,
                s.total,
                s.discount,
                s.payment_received as amount_paid,
                s.change_given,
                pm.method_name as payment_method,
                cc.customer_name,
                cc.phone,
                cc.address
            FROM sales s
            LEFT JOIN payment_methods pm ON s.payment_method_id = pm.id
            LEFT JOIN customer_credit cc ON s.id = cc.sale_id
            WHERE s.receipt_no = ?";

    $stmt = $conn->prepare($sql);
    if (!$stmt) {
        echo json_encode(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
        error_log("Get transaction error: Prepare failed - " . $conn->error);
        exit;
    }
    $stmt->bind_param("s", $receipt_no);
    $stmt->execute();
    $result = $stmt->get_result();

    if ($result->num_rows > 0) {
        $transaction = $result->fetch_assoc();
        $sale_id = $transaction['id'];

        $sql_items = "SELECT 
                        i.item_name as name,
                        si.quantity,
                        si.unit_price as price,
                        si.total_price as total
                      FROM sales_items si
                      JOIN items i ON si.item_id = i.id
                      WHERE si.sale_id = ?";

        $stmt_items = $conn->prepare($sql_items);
        if (!$stmt_items) {
            echo json_encode(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
            error_log("Get transaction error: Prepare failed for items - " . $conn->error);
            exit;
        }
        $stmt_items->bind_param("i", $sale_id);
        $stmt_items->execute();
        $result_items = $stmt_items->get_result();

        $items = [];
        while ($item = $result_items->fetch_assoc()) {
            $items[] = [
                'name' => $item['name'],
                'quantity' => $item['quantity'],
                'price' => $item['price'],
                'total' => $item['total']
            ];
        }

        $customer_info = null;
        if ($transaction['customer_name']) {
            $customer_info = [
                'name' => $transaction['customer_name'],
                'phone' => $transaction['phone'],
                'address' => $transaction['address']
            ];
        }

        $response = [
            'status' => 'success',
            'data' => [
                'receipt_no' => $transaction['receipt_no'],
                'sale_date' => $transaction['sale_date'],
                'items' => $items,
                'total' => $transaction['total'],
                'discount' => $transaction['discount'],
                'amount_paid' => $transaction['amount_paid'],
                'payment_method' => $transaction['payment_method'],
                'customer_info' => $customer_info
            ]
        ];

        echo json_encode($response);
        $stmt_items->close();
    } else {
        echo json_encode([
            'status' => 'error',
            'message' => 'Transaction not found'
        ]);
    }

    $stmt->close();
}

// GET SUPPLIERS
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action']) && $_GET['action'] == 'get_suppliers') {
    $sql = "SELECT id, supplier_name FROM suppliers ORDER BY supplier_name";
    $result = $conn->query($sql);

    $suppliers = [];
    while ($row = $result->fetch_assoc()) {
        $suppliers[] = $row;
    }

    echo json_encode([
        'status' => 'success',
        'data' => $suppliers
    ]);
}

// RESTOCK PRODUCT
elseif ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($data['action']) && $data['action'] == 'restock_product') {
    $required_fields = ['item_id', 'quantity', 'supplier_id'];
    foreach ($required_fields as $field) {
        if (!isset($data[$field])) {
            echo json_encode(['status' => 'error', 'message' => "$field is required"]);
            error_log("Restock product error: Missing $field");
            exit;
        }
    }

    $item_id = (int)$data['item_id'];
    $quantity = (int)$data['quantity'];
    $supplier_id = (int)$data['supplier_id'];
    $price_cost = isset($data['price_cost']) ? (float)$data['price_cost'] : 0;
    $invoice_no = isset($data['invoice_no']) ? $conn->real_escape_string($data['invoice_no']) : '';
    $notes = isset($data['notes']) ? $conn->real_escape_string($data['notes']) : '';
    $user_id = isset($data['user_id']) ? (int)$data['user_id'] : 1;

    $conn->begin_transaction();

    try {
        $sql = "INSERT INTO supplier_prices (
                  item_id, supplier_id, stock_per_unit, 
                  supplier_price_unit, price_cost,
                  invoice_no, notes, date_keyin, user_id
               ) VALUES (?, ?, ?, ?, ?, ?, ?, NOW(), ?)";
        $stmt = $conn->prepare($sql);
        if (!$stmt) {
            throw new Exception("Prepare failed for supplier_prices: " . $conn->error);
        }
        $stmt->bind_param(
            "iiiddssi", 
            $item_id, $supplier_id, $quantity,
            $price_cost, $price_cost,
            $invoice_no, $notes, $user_id
        );

        if (!$stmt->execute()) {
            throw new Exception("Failed to insert supplier price: " . $stmt->error);
        }
        $stmt->close();

        $sql = "INSERT INTO stock_history (
                  item_id, supplier_id, quantity,
                  price_cost, invoice_no, notes,
                  user_id, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, NOW())";
        $stmt = $conn->prepare($sql);
        if (!$stmt) {
            throw new Exception("Prepare failed for stock_history: " . $conn->error);
        }
        $stmt->bind_param(
            "iiidssi", 
            $item_id, $supplier_id, $quantity,
            $price_cost, $invoice_no, $notes,
            $user_id
        );

        if (!$stmt->execute()) {
            throw new Exception("Failed to insert stock history: " . $stmt->error);
        }
        $stmt->close();

        $stock_sql = "SELECT 
                         COALESCE(SUM(stock_per_unit), 0) as stock 
                      FROM supplier_prices 
                      WHERE item_id = ?";
        $stmt = $conn->prepare($stock_sql);
        if (!$stmt) {
            throw new Exception("Prepare failed for stock query: " . $conn->error);
        }
        $stmt->bind_param("i", $item_id);
        $stmt->execute();
        $stock = $stmt->get_result()->fetch_assoc();
        $stmt->close();

        $conn->commit();

        echo json_encode([
            'status' => 'success',
            'message' => 'Product restocked successfully',
            'data' => [
                'item_id' => $item_id,
                'quantity_added' => $quantity,
                'new_stock' => (int)$stock['stock'],
                'supplier_id' => $supplier_id
            ]
        ]);

    } catch (Exception $e) {
        $conn->rollback();
        echo json_encode([
            'status' => 'error',
            'message' => 'Restock failed: ' . $e->getMessage()
        ]);
        error_log("Restock product error: " . $e->getMessage());
    }
}

// GET PRODUCT DETAILS
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action']) && $_GET['action'] == 'get_product_details' && isset($_GET['item_id'])) {
    $item_id = (int)$_GET['item_id'];

    $product_sql = "SELECT 
                       i.id, i.item_name, i.barcode_per_unit,
                       c.category_name
                    FROM items i
                    LEFT JOIN categories c ON i.category_id = c.id
                    WHERE i.id = ?";
    $stmt = $conn->prepare($product_sql);
    if (!$stmt) {
        echo json_encode(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
        error_log("Get product details error: Prepare failed - " . $conn->error);
        exit;
    }
    $stmt->bind_param("i", $item_id);
    $stmt->execute();
    $product = $stmt->get_result()->fetch_assoc();
    $stmt->close();

    if (!$product) {
        echo json_encode(['status' => 'error', 'message' => 'Product not found']);
        exit;
    }

    $stock_sql = "SELECT 
                     COALESCE(SUM(stock_per_unit), 0) as total_stock,
                     COUNT(DISTINCT supplier_id) as supplier_count
                  FROM supplier_prices
                  WHERE item_id = ?";
    $stmt = $conn->prepare($stock_sql);
    if (!$stmt) {
        echo json_encode(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
        error_log("Get product details error: Prepare failed for stock - " . $conn->error);
        exit;
    }
    $stmt->bind_param("i", $item_id);
    $stmt->execute();
    $stock_info = $stmt->get_result()->fetch_assoc();
    $stmt->close();

    $price_sql = "SELECT 
                     sp.supplier_price_unit, sp.price_cost,
                     s.supplier_name, sp.date_keyin
                  FROM supplier_prices sp
                  LEFT JOIN suppliers s ON sp.supplier_id = s.id
                  WHERE sp.item_id = ?
                  ORDER BY sp.date_keyin DESC
                  LIMIT 1";
    $stmt = $conn->prepare($price_sql);
    if (!$stmt) {
        echo json_encode(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
        error_log("Get product details error: Prepare failed for price - " . $conn->error);
        exit;
    }
    $stmt->bind_param("i", $item_id);
    $stmt->execute();
    $price_info = $stmt->get_result()->fetch_assoc();
    $stmt->close();

    $suppliers_sql = "SELECT 
                         DISTINCT s.id, s.supplier_name
                      FROM supplier_prices sp
                      JOIN suppliers s ON sp.supplier_id = s.id
                      WHERE sp.item_id = ?";
    $stmt = $conn->prepare($suppliers_sql);
    if (!$stmt) {
        echo json_encode(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
        error_log("Get product details error: Prepare failed for suppliers - " . $conn->error);
        exit;
    }
    $stmt->bind_param("i", $item_id);
    $stmt->execute();
    $suppliers = $stmt->get_result()->fetch_all(MYSQLI_ASSOC);
    $stmt->close();

    $response = [
        'status' => 'success',
        'data' => [
            'product' => [
                'id' => $product['id'],
                'name' => $product['item_name'],
                'barcode' => $product['barcode_per_unit'],
                'category' => $product['category_name']
            ],
            'stock' => [
                'total' => (int)$stock_info['total_stock'],
                'supplier_count' => (int)$stock_info['supplier_count']
            ],
            'last_price' => $price_info ? [
                'supplier_price_unit' => $price_info['supplier_price_unit'],
                'price_cost' => $price_info['price_cost'],
                'supplier_name' => $price_info['supplier_name'],
                'date' => $price_info['date_keyin']
            ] : null,
            'suppliers' => $suppliers
        ]
    ];

    echo json_encode($response);
}

// GET PRODUCT BY NAME
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action']) && $_GET['action'] == 'get_product_by_name' && isset($_GET['name'])) {
    $name = $conn->real_escape_string($_GET['name']);

    $sql = "SELECT 
               i.id, 
               i.item_name as name,
               i.barcode_per_unit as barcode,
               (SELECT sp.supplier_price_unit 
                FROM supplier_prices sp 
                WHERE sp.item_id = i.id 
                ORDER BY sp.date_keyin DESC 
                LIMIT 1) as price,
               (COALESCE(SUM(sp.stock_per_unit), 0) - 
               COALESCE((SELECT SUM(si.quantity) 
                        FROM sales_items si
                        JOIN sales s ON si.sale_id = s.id
                        WHERE si.item_id = i.id), 0)) as stock
            FROM items i
            LEFT JOIN supplier_prices sp ON i.id = sp.item_id
            WHERE i.item_name = ?
            GROUP BY i.id
            LIMIT 1";

    $stmt = $conn->prepare($sql);
    if (!$stmt) {
        echo json_encode(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
        error_log("Get product by name error: Prepare failed - " . $conn->error);
        exit;
    }
    $stmt->bind_param("s", $name);
    $stmt->execute();
    $result = $stmt->get_result();

    if ($result->num_rows > 0) {
        $product = $result->fetch_assoc();
        echo json_encode([
            'status' => 'success',
            'data' => [
                'id' => $product['id'],
                'name' => $product['name'],
                'barcode' => $product['barcode'],
                'price' => $product['price'],
                'stock' => (int)$product['stock']
            ]
        ]);
    } else {
        echo json_encode([
            'status' => 'error',
            'message' => 'Product not found'
        ]);
    }
    $stmt->close();
}

// GET PRODUCT FOR RESTOCK
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action']) && $_GET['action'] == 'get_product_for_restock' && isset($_GET['item_id'])) {
    $item_id = (int)$_GET['item_id'];

    $product_sql = "SELECT id, item_name, barcode_per_unit FROM items WHERE id = ?";
    $stmt = $conn->prepare($product_sql);
    if (!$stmt) {
        echo json_encode(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
        error_log("Get product for restock error: Prepare failed - " . $conn->error);
        exit;
    }
    $stmt->bind_param("i", $item_id);
    $stmt->execute();
    $product = $stmt->get_result()->fetch_assoc();
    $stmt->close();

    if (!$product) {
        echo json_encode(['status' => 'error', 'message' => 'Product not found']);
        exit;
    }

    $stock_sql = "SELECT 
                     COALESCE(SUM(stock_per_unit), 0) as stock 
                  FROM supplier_prices 
                  WHERE item_id = ?";
    $stmt = $conn->prepare($stock_sql);
    if (!$stmt) {
        echo json_encode(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
        error_log("Get product for restock error: Prepare failed for stock - " . $conn->error);
        exit;
    }
    $stmt->bind_param("i", $item_id);
    $stmt->execute();
    $stock = $stmt->get_result()->fetch_assoc();
    $stmt->close();

    $suppliers_sql = "SELECT s.id, s.supplier_name 
                     FROM suppliers s
                     ORDER BY s.supplier_name";
    $stmt = $conn->prepare($suppliers_sql);
    if (!$stmt) {
        echo json_encode(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
        error_log("Get product for restock error: Prepare failed for suppliers - " . $conn->error);
        exit;
    }
    $stmt->execute();
    $suppliers = $stmt->get_result()->fetch_all(MYSQLI_ASSOC);
    $stmt->close();

    $price_sql = "SELECT 
                     sp.supplier_price_unit, 
                     sp.price_cost,
                     sp.invoice_no
                  FROM supplier_prices sp
                  WHERE sp.item_id = ? 
                  ORDER BY sp.date_keyin DESC 
                  LIMIT 1";
    $stmt = $conn->prepare($price_sql);
    if (!$stmt) {
        echo json_encode(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
        error_log("Get product for restock error: Prepare failed for price - " . $conn->error);
        exit;
    }
    $stmt->bind_param("i", $item_id);
    $stmt->execute();
    $price = $stmt->get_result()->fetch_assoc();
    $stmt->close();

    echo json_encode([
        'status' => 'success',
        'data' => [
            'product' => $product,
            'stock' => (int)$stock['stock'],
            'suppliers' => $suppliers,
            'last_price' => $price ? [
                'supplier_price_unit' => $price['supplier_price_unit'],
                'price_cost' => $price['price_cost'],
                'invoice_no' => $price['invoice_no']
            ] : null
        ]
    ]);
}

// CLOSE SHIFT
elseif ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($data['action']) && $data['action'] == 'close_shift') {
    if (!isset($data['user_id']) || !isset($data['cash_end'])) {
        echo json_encode(['status' => 'error', 'message' => 'user_id and cash_end required']);
        exit;
    }
    $user_id = (int)$data['user_id'];
    $cash_end = (float)$data['cash_end'];

    // Cari shift yang masih aktif (shift_end IS NULL)
    $sql = "SELECT id, cash_start, cash_end FROM shifts WHERE user_id = ? AND shift_end IS NULL ORDER BY shift_start DESC LIMIT 1";
    $stmt = $conn->prepare($sql);
    $stmt->bind_param("i", $user_id);
    $stmt->execute();
    $result = $stmt->get_result();
    if ($shift = $result->fetch_assoc()) {
        $shift_id = $shift['id'];
        $cash_start = (float)$shift['cash_start'];
        $expected_cash = (float)$shift['cash_end'];
        $difference = $cash_end - $expected_cash;
        $now = date('Y-m-d H:i:s');
        $sql_update = "UPDATE shifts SET shift_end = ?, cash_end = ?, expected_cash = ?, cash_difference = ? WHERE id = ?";
        $stmt2 = $conn->prepare($sql_update);
        $stmt2->bind_param("sdddi", $now, $cash_end, $expected_cash, $difference, $shift_id);
        if ($stmt2->execute()) {
            echo json_encode(['status' => 'success', 'message' => 'Shift closed successfully']);
        } else {
            echo json_encode(['status' => 'error', 'message' => 'Failed to close shift: ' . $stmt2->error]);
        }
        $stmt2->close();
    } else {
        echo json_encode(['status' => 'error', 'message' => 'No active shift found']);
    }
    $stmt->close();
}

// START SHIFT - TAMBAHKAN BLOK INI
elseif ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($data['action']) && $data['action'] == 'start_shift') {
    if (!isset($data['user_id']) || !isset($data['cash_start'])) {
        echo json_encode(['status' => 'error', 'message' => 'user_id dan cash_start diperlukan']);
        exit;
    }
    $user_id = (int)$data['user_id'];
    $cash_start = (float)$data['cash_start'];
    $now = date('Y-m-d H:i:s');

    // Pastikan tiada shift aktif
    $sql = "SELECT id FROM shifts WHERE user_id = ? AND shift_end IS NULL";
    $stmt = $conn->prepare($sql);
    $stmt->bind_param("i", $user_id);
    $stmt->execute();
    $result = $stmt->get_result();
    if ($result->num_rows > 0) {
        echo json_encode(['status' => 'error', 'message' => 'Shift sudah bermula untuk user ini']);
        $stmt->close();
        exit;
    }
    $stmt->close();

    // Insert shift baru
    $sql = "INSERT INTO shifts (user_id, cash_start, cash_end, shift_start) VALUES (?, ?, ?, ?)";
    $stmt = $conn->prepare($sql);
    $stmt->bind_param("idds", $user_id, $cash_start, $cash_start, $now);
    if ($stmt->execute()) {
        echo json_encode(['status' => 'success', 'message' => 'Shift bermula!']);
    } else {
        echo json_encode(['status' => 'error', 'message' => 'Gagal mula shift: ' . $stmt->error]);
    }
    $stmt->close();
}

// GET STORE INFO
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action']) && $_GET['action'] == 'get_store_info') {
    $sql = "SELECT * FROM store_settings LIMIT 1";
    $result = $conn->query($sql);
    if ($result->num_rows > 0) {
        echo json_encode($result->fetch_assoc());
    } else {
        echo json_encode(['status' => 'error', 'message' => 'Store info not found']);
    }
}

// DEFAULT ERROR
else {
    echo json_encode(['status' => 'error', 'message' => 'Invalid request or action']);
    error_log("Invalid request: " . $_SERVER['REQUEST_METHOD'] . " " . $_SERVER['REQUEST_URI']);
}

$conn->close();
?>
