from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, database
from .auth import get_current_user
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy import func

router = APIRouter(
    prefix="/hr",
    tags=["hr"]
)

get_db = database.get_db

class EmployeeCreate(BaseModel):
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    role_function: Optional[str] = None
    salary: float = 0.0
    vacation_days_available: int = 14
    user_id: Optional[int] = None

class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    role_function: Optional[str] = None
    salary: Optional[float] = None
    vacation_days_available: Optional[int] = None
    absent_days_this_month: Optional[int] = None

@router.get("/employees")
def get_employees(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Unauthorized")
    return db.query(models.Employee).all()

@router.post("/employees")
def create_employee(employee: EmployeeCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Unauthorized")
    db_emp = models.Employee(
        first_name=employee.first_name,
        last_name=employee.last_name,
        email=employee.email,
        phone=employee.phone,
        address=employee.address,
        role_function=employee.role_function,
        salary=employee.salary,
        vacation_days_available=employee.vacation_days_available,
        user_id=employee.user_id,
        hire_date=datetime.now()
    )
    db.add(db_emp)
    db.commit()
    db.refresh(db_emp)
    return db_emp

@router.put("/employees/{emp_id}")
def update_employee(emp_id: int, employee: EmployeeUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Unauthorized")
    db_emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
    if not db_emp:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    for var, value in vars(employee).items():
        if value is not None:
            setattr(db_emp, var, value)
            
    db.commit()
    db.refresh(db_emp)
    return db_emp

@router.delete("/employees/{emp_id}")
def delete_employee(emp_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Unauthorized")
    db_emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
    if not db_emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.delete(db_emp)
    db.commit()
    return {"status": "success"}

@router.post("/employees/{emp_id}/pay")
def pay_employee(emp_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Unauthorized")
    db_emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
    if not db_emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Get commissions if user_id is linked (dummy logic for now)
    commissions = 0.0
    if db_emp.user_id:
        # Example logic: calculate commissions from sales
        pass
        
    # Reset absent days for the new month
    db_emp.absent_days_this_month = 0
    db.commit()
    
    return {
        "status": "success",
        "message": f"Pago generado para {db_emp.first_name}.",
        "details": {
            "base_salary": float(db_emp.salary or 0),
            "commissions": commissions,
            "total_payout": float(db_emp.salary or 0) + commissions
        }
    }
